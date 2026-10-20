"""文件角色关联的条件查询和角色删除时的关联清理。"""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from model.file_role_info import FileRoleInfo


def list_items(
    session: Session, file_id: int | None = None, role_id: int | None = None,
) -> list[FileRoleInfo]:
    """按文件和角色筛选，未传入的条件不参与筛选。"""
    query = select(FileRoleInfo).order_by(col(FileRoleInfo.id))
    if file_id is not None:
        query = query.where(col(FileRoleInfo.file_id) == file_id)
    if role_id is not None:
        query = query.where(col(FileRoleInfo.role_id) == role_id)
    return list(session.exec(query).all())


def delete_by_role(session: Session, role_id: int) -> None:
    """在调用方事务中清理角色的文件授权。"""
    session.exec(delete(FileRoleInfo).where(col(FileRoleInfo.role_id) == role_id))
