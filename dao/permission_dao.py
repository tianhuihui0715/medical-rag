"""权限的自定义查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.permission_info import PermissionInfo


def list_permissions(session: Session) -> list[PermissionInfo]:
    query = select(PermissionInfo).order_by(col(PermissionInfo.id))
    return list(session.exec(query).all())
