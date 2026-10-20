"""用户角色关联的条件查询及批量清理语句，使用业务层传入的会话。"""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from model.user_role_info import UserRoleInfo


def list_items(
    session: Session, user_id: int | None = None, role_id: int | None = None,
) -> list[UserRoleInfo]:
    """按用户和角色筛选；未传入的条件不参与筛选。"""
    query = select(UserRoleInfo).order_by(col(UserRoleInfo.id))
    if user_id is not None:
        query = query.where(col(UserRoleInfo.user_id) == user_id)
    if role_id is not None:
        query = query.where(col(UserRoleInfo.role_id) == role_id)
    return list(session.exec(query).all())


def delete_by_user(session: Session, user_id: int) -> None:
    session.exec(delete(UserRoleInfo).where(col(UserRoleInfo.user_id) == user_id))


def delete_by_role(session: Session, role_id: int) -> None:
    session.exec(delete(UserRoleInfo).where(col(UserRoleInfo.role_id) == role_id))
