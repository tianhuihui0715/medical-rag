"""按文件类型选择父子切块策略，统一切块调用入口。"""

from langchain_core.documents import Document

from splitter.md_splitter import MdSplitter
from splitter.text_splitter import TextSplitter


class FileSplitter:
    """当前支持 TXT 和 Markdown，后续文件类型在这里扩展策略。"""
    def __init__(self, extension: str, parent_size: int, child_size: int, overlap: int):
        strategies = {"txt": TextSplitter, "md": MdSplitter}
        strategy = strategies.get(extension.lower())
        if strategy is None:
            raise ValueError("当前仅支持 txt、md 文件切块")
        self.strategy = strategy(parent_size, child_size, overlap)

    def split(self, documents: list[Document]) -> list[tuple[Document, list[Document]]]:
        return self.strategy.split(documents)
