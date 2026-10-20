"""模型服务配置实体，保存云端地址、密钥和请求超时。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class ModelProviderFields(SQLModel):
    name: str = Field(sa_type=Text)
    base_url: str = Field(sa_type=Text)  # API 根地址，包含服务要求的版本前缀。
    timeout: float = 60  # 单次网络读写等操作的超时时间，单位秒。
    enabled: bool = True
    description: str = Field(default="", sa_type=Text)


class ModelProviderCreate(ModelProviderFields):
    api_key: str = Field(default="", sa_type=Text)


class ModelProviderUpdate(ModelProviderFields):
    api_key: str | None = None  # 不传或传 None 时保留原密钥。


class ModelProviderInfo(ModelProviderCreate, BaseEntity, table=True):
    """服务配置表；多个模型可共用同一配置。"""
    __tablename__ = "model_provider"  # pyright: ignore[reportAssignmentType]


class ModelProviderRead(ModelProviderFields, BaseEntity):
    """管理接口的响应不返回 API 密钥。"""
