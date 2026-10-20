"""用户角色关联表实体及对应的请求模型。"""

from sqlmodel import SQLModel

from model.base_entity import BaseEntity


class UserRoleCreate(SQLModel):
    user_id: int
    role_id: int


class UserRoleInfo(UserRoleCreate, BaseEntity, table=True):
    """用户角色关联的数据库实体。"""
    __tablename__ = "user_role"  # pyright: ignore[reportAssignmentType]
