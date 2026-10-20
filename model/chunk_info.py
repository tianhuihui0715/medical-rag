"""父子切块实体，保存切块文本及其文件和页码来源。"""

from typing import Any

from sqlalchemy import JSON, Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class ChunkInfo(BaseEntity, table=True):
    """父块的 parent_id 为空；子块通过 parent_id 定位父块。"""
    __tablename__ = "chunk_info"  # pyright: ignore[reportAssignmentType]

    file_id: int
    parent_id: int | None = None
    content: str = Field(sa_type=Text)
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None
    content_hash: str = Field(default="", sa_type=Text)  # 切块文本哈希，不作为主键。
    meta: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)  # 标题路径、结构类别和原文位置。


class SplitOptions(SQLModel):
    """单次切块参数；未提供的值由业务层读取数据库默认配置。"""
    parent_size: int | None = None
    child_size: int | None = None
    overlap: int | None = None


class SplitRequest(SplitOptions):
    """多个文件共用本次切块参数，缺省项使用数据库默认配置。"""
    file_ids: list[int]
