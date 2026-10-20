"""权限角色关联的条件查询及批量清理语句，使用业务层传入的会话。"""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from model.permission_role_info import PermissionRoleInfo


def list_items(
    session: Session, permission_id: int | None = None, role_id: int | None = None,
) -> list[PermissionRoleInfo]:
    """按权限和角色筛选；未传入的条件不参与筛选。"""
    query = select(PermissionRoleInfo).order_by(col(PermissionRoleInfo.id))
    if permission_id is not None:
        query = query.where(col(PermissionRoleInfo.permission_id) == permission_id)
    if role_id is not None:
        query = query.where(col(PermissionRoleInfo.role_id) == role_id)
    return list(session.exec(query).all())


def delete_by_permission(session: Session, permission_id: int) -> None:
    session.exec(
        delete(PermissionRoleInfo).where(col(PermissionRoleInfo.permission_id) == permission_id)
    )


def delete_by_role(session: Session, role_id: int) -> None:
    session.exec(delete(PermissionRoleInfo).where(col(PermissionRoleInfo.role_id) == role_id))
