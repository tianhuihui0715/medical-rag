"""知识库实体及维护资料的请求模型，文件归属由知识库文件关联表记录。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class KnowledgeBaseUpdate(SQLModel):
    name: str = Field(sa_type=Text, sa_column_kwargs={"comment": "知识库名称"})
    description: str = Field(
        default="", sa_type=Text, sa_column_kwargs={"comment": "知识库说明"},
    )
    enabled: bool = Field(default=True, sa_column_kwargs={"comment": "是否启用：1 启用，0 停用"})


class KnowledgeBaseCreate(KnowledgeBaseUpdate):
    pass


class KnowledgeBaseInfo(KnowledgeBaseCreate, BaseEntity, table=True):
    """保存知识库资料；一个知识库可通过关联表包含多个文件。"""
    __tablename__ = "knowledge_base"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"comment": "知识库表"}
