"""权限用户关联表实体及对应的请求模型。"""

from sqlmodel import SQLModel

from model.base_entity import BaseEntity


class PermissionUserCreate(SQLModel):
    permission_id: int
    user_id: int


class PermissionUserInfo(PermissionUserCreate, BaseEntity, table=True):
    """权限用户关联的数据库实体。"""
    __tablename__ = "permission_user"  # pyright: ignore[reportAssignmentType]
