"""模型实体及聊天、本地和远程向量化、重排调用的请求结构。"""

from typing import Any

from sqlalchemy import JSON, Text, text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class ModelUpdate(SQLModel):
    provider_id: int
    name: str = Field(sa_type=Text)  # 云平台实际使用的模型名称。
    kind: str = Field(sa_type=Text)  # chat、embedding 或 rerank。
    api_path: str = Field(default="", sa_type=Text)  # 留空时按用途选择标准路径。
    params: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    enabled: bool = True
    description: str = Field(default="", sa_type=Text)


class ModelCreate(ModelUpdate):
    pass


class ModelInfo(ModelCreate, BaseEntity, table=True):
    """保存模型与服务配置的对应关系及默认调用参数。"""
    __tablename__ = "model_info"  # pyright: ignore[reportAssignmentType]

    # 仅通过默认模型切换接口修改，普通资料更新不会清除当前选择。
    is_default: bool = Field(
        default=False,
        sa_column_kwargs={
            "server_default": text("0"),
            "comment": "是否为同用途的系统默认模型：1 是，0 否",
        },
    )


class ChatRequest(SQLModel):
    messages: list[dict[str, Any]]


class EmbeddingRequest(SQLModel):
    input: str | list[str]


class LocalEmbeddingRequest(EmbeddingRequest):
    model: str = "bge-m3"


class RerankRequest(SQLModel):
    query: str
    documents: list[str]
    top_n: int | None = None


class LocalRerankRequest(RerankRequest):
    model: str = "bge-reranker-large"
