"""字典表实体及对应的请求模型。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class DictUpdate(SQLModel):
    value: str = Field(sa_type=Text)
    description: str = Field(default="", sa_type=Text)


class DictCreate(DictUpdate):
    dict_type: str = Field(index=True)
    parent_id: int | None = Field(default=None, index=True)


class DictInfo(DictCreate, BaseEntity, table=True):
    """字典的数据库实体。"""
    __tablename__ = "dict_info"  # pyright: ignore[reportAssignmentType]
