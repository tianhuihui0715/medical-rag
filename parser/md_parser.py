"""按 Markdown 语法节点保留标题层级、段落、表格、列表及代码边界。"""

from collections.abc import Iterator
from typing import Any

from langchain_community.document_loaders import TextLoader
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from markdown_it import MarkdownIt

from parser.file_parser import FileParser


class MarkdownLoader(BaseLoader):
    """用语法节点定位原文，输出兼容现有 JSON 存储的 Document。"""
    def __init__(self, path: str):
        self.path = path

    def lazy_load(self) -> Iterator[Document]:
        text = TextLoader(self.path, encoding="utf-8-sig", autodetect_encoding=True).load()[0].page_content
        lines = text.splitlines(keepends=True)
        tokens = MarkdownIt("commonmark").enable("table").parse(text)
        headings: list[tuple[int, str]] = []
        for index, token in enumerate(tokens):
            # 顶层节点覆盖嵌套列表、引用等完整结构，避免把内部正文重复输出。
            if token.level != 0 or token.map is None:
                continue
            start, end = token.map
            category = {
                "heading_open": "Title", "paragraph_open": "NarrativeText",
                "table_open": "Table", "fence": "CodeSnippet", "code_block": "CodeSnippet",
                "bullet_list_open": "List", "ordered_list_open": "List",
                "blockquote_open": "BlockQuote",
            }.get(token.type, "UncategorizedText")
            if category == "Title":
                level = int(token.tag[1:])
                while headings and headings[-1][0] >= level:
                    headings.pop()
                headings.append((level, tokens[index + 1].content))
            metadata: dict[str, Any] = {
                "parser": "markdown-it", "category": category,
                "section": [title for _, title in headings],
                "line_start": start + 1, "line_end": end,
                "prefix_lines": 0, "suffix_lines": 0,
            }
            units: list[list[int]] = []
            if category == "Title":
                metadata["heading_level"] = int(token.tag[1:])
            elif category in ("Table", "List"):
                node_type = "tr_open" if category == "Table" else "list_item_open"
                depth = 2 if category == "Table" else 1
                for child in tokens[index + 1:]:
                    if child.level == 0:
                        break
                    if child.type == node_type and child.level == depth and child.map:
                        units.append([child.map[0] - start, child.map[1] - start])
                if category == "Table":
                    # 表头及分隔行在每个表格分片中重复，数据行作为不可截断的单位。
                    units = units[1:]
                    metadata["prefix_lines"] = units[0][0] if units else end - start
            elif category == "CodeSnippet":
                metadata["language"] = token.info.strip().split()[0] if token.info.strip() else ""
                if token.type == "fence":
                    metadata["prefix_lines"] = 1
                    closing = lines[end - 1].strip()
                    metadata["suffix_lines"] = int(
                        end - start > 1 and len(closing) >= len(token.markup)
                        and set(closing) == {token.markup[0]}
                    )
                units = [[line, line + 1] for line in range(
                    metadata["prefix_lines"], end - start - metadata["suffix_lines"],
                )]
            if units:
                metadata["units"] = units
            yield Document(page_content="".join(lines[start:end]), metadata=metadata)


def parse(file_id: int) -> list[Document]:
    """按文件 ID 解析 Markdown，结构信息随正文一起持久化。"""
    return FileParser().parse(file_id, MarkdownLoader)
