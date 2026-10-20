"""按章节生成 Markdown 父子块，保护表格行、代码行及列表条目。"""

from langchain_core.documents import Document

from splitter.text_splitter import TextSplitter


class MdSplitter(TextSplitter):
    """正文在章节内递归切分；结构块按完整单位分组，不应用字符重叠。"""
    def parents(self, documents: list[Document]) -> list[Document]:
        if any(document.metadata.get("parser") != "markdown-it" for document in documents):
            raise ValueError("Markdown 解析结果版本较旧，请先重新解析文件")
        parents: list[Document] = []
        paragraphs: list[Document] = []
        titles: list[Document] = []

        def flush() -> None:
            if not paragraphs:
                return
            metadata = dict(paragraphs[0].metadata)
            metadata["line_end"] = paragraphs[-1].metadata.get("line_end")
            combined = Document(
                page_content="\n\n".join(part.page_content.rstrip("\r\n") for part in paragraphs),
                metadata=metadata,
            )
            parents.extend(self.parent.split_documents([combined]))
            paragraphs.clear()

        for document in documents:
            category = document.metadata.get("category")
            if category == "Title":
                flush()
                titles.append(document)
                continue
            if category in ("Table", "CodeSnippet", "List"):
                flush()
                parents.extend(self._structured(document, self.parent_size))
            else:
                if paragraphs and paragraphs[0].metadata.get("section") != document.metadata.get("section"):
                    flush()
                paragraphs.append(document)
        flush()
        # 标题通过 section 元数据关联正文，纯标题文档仍保留可检索的内容。
        return parents if parents else super().parents(titles)

    def children(self, parent: Document) -> list[Document]:
        if parent.metadata.get("category") in ("Table", "CodeSnippet", "List"):
            return self._structured(parent, self.child_size)
        return super().children(parent)

    def _structured(self, document: Document, size: int) -> list[Document]:
        """重复表头或代码围栏；单行表格、单行代码可超过目标大小以保留结构。"""
        spans = document.metadata.get("units", [])
        if len(document.page_content) <= size or not spans:
            return [document]
        lines = document.page_content.splitlines(keepends=True)
        prefix_count = document.metadata.get("prefix_lines", 0)
        suffix_count = document.metadata.get("suffix_lines", 0)
        prefix = "".join(lines[:prefix_count])
        suffix = "".join(lines[-suffix_count:]) if suffix_count else ""
        units = ["".join(lines[start:end]) for start, end in spans]
        if document.metadata.get("category") == "List":
            # 仅对超长条目递归细分，普通条目及嵌套列表保持完整。
            units = [
                part + "\n" for unit in units for part in (
                    self._recursive(size, 0).split_text(unit) if len(unit) > size else [unit.rstrip("\r\n")]
                )
            ]
        chunks: list[Document] = []
        pending: list[str] = []
        length = len(prefix) + len(suffix)

        def flush() -> None:
            if not pending:
                return
            metadata = dict(document.metadata)
            offset = prefix_count
            new_spans = []
            for unit in pending:
                end = offset + len(unit.splitlines(keepends=True))
                new_spans.append([offset, end])
                offset = end
            metadata["units"] = new_spans
            chunks.append(Document(page_content=prefix + "".join(pending) + suffix, metadata=metadata))
            pending.clear()

        for unit in units:
            if pending and length + len(unit) > size:
                flush()
                length = len(prefix) + len(suffix)
            pending.append(unit)
            length += len(unit)
        flush()
        return chunks
