"""知识库与文件的多对多关联实体，使去重后的文件可以被多个知识库引用。"""

from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class KnowledgeFileCreate(SQLModel):
    knowledge_id: int = Field(sa_column_kwargs={"comment": "知识库 ID"})
    file_id: int = Field(sa_column_kwargs={"comment": "文件 ID"})


class KnowledgeFileInfo(KnowledgeFileCreate, BaseEntity, table=True):
    """只记录文件归属；解除关联与删除文件本身是不同的业务操作。"""
    __tablename__ = "knowledge_file"  # pyright: ignore[reportAssignmentType]
    __table_args__ = {"comment": "知识库文件关联表"}
