"""权限表实体及对应的请求模型。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class PermissionUpdate(SQLModel):
    name: str = Field(sa_type=Text)
    description: str = Field(default="", sa_type=Text)
    enabled: bool = True


class PermissionCreate(PermissionUpdate):
    code: str = Field(sa_type=Text)


class PermissionInfo(PermissionCreate, BaseEntity, table=True):
    """权限的数据库实体。"""
    __tablename__ = "permission_info"  # pyright: ignore[reportAssignmentType]
