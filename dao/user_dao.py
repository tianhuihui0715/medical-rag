"""用户的自定义查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.user_info import UserInfo


def list_users(session: Session) -> list[UserInfo]:
    query = select(UserInfo).order_by(col(UserInfo.id))
    return list(session.exec(query).all())


def get_by_username(session: Session, username: str) -> UserInfo | None:
    """按登录名查询未删除用户；存在重名时不选择任意账号进行认证。"""
    query = select(UserInfo).where(
        col(UserInfo.username) == username, col(UserInfo.is_deleted) == 0,
    )
    return session.exec(query).one_or_none()
