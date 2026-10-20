"""文件元数据实体，记录文件属性、MinIO 位置及解析和入库状态。"""

from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class FileFields(SQLModel):
    """文件实体和上传响应共用的文件属性。"""
    name: str = Field(sa_type=Text)
    size: int = Field(sa_type=BigInteger)  # 字节
    extension: str = Field(default="", sa_type=Text)  # 不含点号，如 pdf。
    content_type: str = Field(default="", sa_type=Text)
    content_hash: str | None = Field(default=None, sa_type=String(64))  # SHA-256，历史未知哈希为空。
    source_path: str = Field(default="", sa_type=Text)  # 相对路径：部门/职位/文件名，供目录检索过滤。
    bucket: str = Field(default="", sa_type=Text)  # MinIO 桶名。
    object_name: str = Field(default="", sa_type=Text)  # 桶内对象名，用于定位文件。
    parsed_object_name: str = Field(default="", sa_type=Text)  # 解析结果 JSON 的对象名，与原文件共用 bucket。
    # 解析、切块、向量入库分别记录状态：pending、processing、completed、failed。
    parse_status: str = Field(default="pending", sa_type=Text)
    split_status: str = Field(default="pending", sa_type=Text)
    ingest_status: str = Field(default="pending", sa_type=Text)
    embedding_model_id: int | None = None  # 最近成功入库使用的模型，便于追溯。
    vector_collection: str = Field(default="", sa_type=Text)  # 最近成功入库的 Milvus 集合。
    error: str = Field(default="", sa_type=Text)


class FileInfo(FileFields, BaseEntity, table=True):
    """保存文件元数据，通过哈希、大小及删除状态防止重复入库。"""
    __tablename__ = "file_info"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("content_hash", "size", "is_deleted", name="uq_file_content"),
    )


class FileUpload(FileFields, BaseEntity):
    """返回文件和本次关联的知识库 ID，并说明是否复用已有文件。"""
    knowledge_id: int
    upload_name: str
    duplicate: bool
    message: str


class FileRead(BaseEntity):
    """可检索文件列表的响应，不暴露对象存储内部路径。"""
    name: str
    size: int
    extension: str
    content_type: str
    parse_status: str
    split_status: str
    ingest_status: str


class ParseRequest(SQLModel):
    """解析任务请求，单个文件也通过只有一个元素的列表提交。"""
    file_ids: list[int]
