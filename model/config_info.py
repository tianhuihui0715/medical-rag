"""配置表实体及对应的请求模型。"""

from sqlalchemy import Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class ConfigUpdate(SQLModel):
    value: str = Field(sa_type=Text)
    use_dict: int = 0  # 非零时，value 保存字典类型，由业务层解析为值列表。
    category: str = Field(index=True)
    description: str = Field(default="", sa_type=Text)


class ConfigCreate(ConfigUpdate):
    key: str


class ConfigInfo(ConfigCreate, BaseEntity, table=True):
    """配置的数据库实体。"""
    __tablename__ = "config_info"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (UniqueConstraint("key", name="uq_config_key"),)
