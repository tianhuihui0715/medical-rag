"""权限角色关联表实体及对应的请求模型。"""

from sqlmodel import SQLModel

from model.base_entity import BaseEntity


class PermissionRoleCreate(SQLModel):
    permission_id: int
    role_id: int


class PermissionRoleInfo(PermissionRoleCreate, BaseEntity, table=True):
    """权限角色关联的数据库实体。"""
    __tablename__ = "permission_role"  # pyright: ignore[reportAssignmentType]
