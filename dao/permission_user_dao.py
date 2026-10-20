"""权限用户关联的条件查询及批量清理语句，使用业务层传入的会话。"""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from model.permission_user_info import PermissionUserInfo


def list_items(
    session: Session, permission_id: int | None = None, user_id: int | None = None,
) -> list[PermissionUserInfo]:
    """按权限和用户筛选；未传入的条件不参与筛选。"""
    query = select(PermissionUserInfo).order_by(col(PermissionUserInfo.id))
    if permission_id is not None:
        query = query.where(col(PermissionUserInfo.permission_id) == permission_id)
    if user_id is not None:
        query = query.where(col(PermissionUserInfo.user_id) == user_id)
    return list(session.exec(query).all())


def delete_by_permission(session: Session, permission_id: int) -> None:
    session.exec(
        delete(PermissionUserInfo).where(col(PermissionUserInfo.permission_id) == permission_id)
    )


def delete_by_user(session: Session, user_id: int) -> None:
    session.exec(delete(PermissionUserInfo).where(col(PermissionUserInfo.user_id) == user_id))
