"""角色表实体及对应的请求模型。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class RoleUpdate(SQLModel):
    name: str = Field(sa_type=Text)
    description: str = Field(default="", sa_type=Text)
    enabled: bool = True


class RoleCreate(RoleUpdate):
    code: str = Field(sa_type=Text)


class RoleInfo(RoleCreate, BaseEntity, table=True):
    """角色的数据库实体。"""
    __tablename__ = "role_info"  # pyright: ignore[reportAssignmentType]
