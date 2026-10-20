"""使用 LangChain 按段落和中英文标点递归生成正文父子块。"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextSplitter:
    """父块不重叠，子块只在所属父块内部应用目标重叠量；大小按字符计算。"""
    def __init__(self, parent_size: int, child_size: int, overlap: int):
        self.parent_size = parent_size
        self.child_size = child_size
        self.parent = self._recursive(parent_size, 0)
        self.child = self._recursive(child_size, overlap)

    @staticmethod
    def _recursive(size: int, overlap: int) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            chunk_size=size, chunk_overlap=overlap, keep_separator="end",
            separators=["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "，", " ", ""],
        )

    def split(self, documents: list[Document]) -> list[tuple[Document, list[Document]]]:
        """返回父块及其子块，来源元数据由 LangChain 传递。"""
        return [(parent, self.children(parent)) for parent in self.parents(documents)]

    def parents(self, documents: list[Document]) -> list[Document]:
        return self.parent.split_documents(documents)

    def children(self, parent: Document) -> list[Document]:
        return self.child.split_documents([parent])
