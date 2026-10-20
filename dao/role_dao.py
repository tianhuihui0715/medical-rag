"""角色的自定义查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.role_info import RoleInfo


def list_roles(session: Session) -> list[RoleInfo]:
    query = select(RoleInfo).order_by(col(RoleInfo.id))
    return list(session.exec(query).all())
