"""使用 LangChain TextLoader 解析纯文本文件。"""

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from parser.file_parser import FileParser


def parse(file_id: int) -> list[Document]:
    """按文件 ID 读取源文件，优先 UTF-8，必要时由 Loader 自动识别编码。"""
    return FileParser().parse(
        file_id, lambda path: TextLoader(path, encoding="utf-8-sig", autodetect_encoding=True),
    )
