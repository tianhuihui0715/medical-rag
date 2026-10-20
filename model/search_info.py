"""统一检索的入参和输出，召回数量与最终块数均可覆盖配置默认值。"""

from typing import Any

from sqlmodel import Field, SQLModel


class SearchRequest(SQLModel):
    query: str
    knowledge_ids: list[int] | None = None
    recall_k: int | None = None
    top_k: int | None = None
    sparse_weight: float | None = None


class DirectorySearchRequest(SQLModel):
    query: str
    top_k: int | None = None
    department: str
    position: str


class SearchBlock(SQLModel):
    file_id: int
    file_name: str
    parent_id: int
    content: str
    page_start: int | None = None
    page_end: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    child_ids: list[int]
    questions: list[str]
    fusion_score: float
    score: float  # 重排相关性分数，最终按此值降序返回。


class SearchResult(SQLModel):
    query: str
    questions: list[str] = Field(default_factory=list)
    knowledge_ids: list[int] = Field(default_factory=list)
    blocks: list[SearchBlock] = Field(default_factory=list)
