"""文件角色关联实体，记录允许访问文件的角色。"""

from sqlmodel import SQLModel

from model.base_entity import BaseEntity


class FileRoleCreate(SQLModel):
    file_id: int
    role_id: int


class FileRoleInfo(FileRoleCreate, BaseEntity, table=True):
    """一个文件可以关联多个角色，用户命中任意授权角色即可访问。"""
    __tablename__ = "file_role"  # pyright: ignore[reportAssignmentType]
