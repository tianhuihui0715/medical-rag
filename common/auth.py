"""读取会话 Cookie，并提供当前登录用户依赖。"""

from fastapi import Depends, HTTPException, Request
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from model.user_info import UserInfo
from service.user_service import UserService

SESSION_COOKIE = "session_id"


def get_session_id(request: Request) -> str:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise HTTPException(401, "请先登录")
    return session_id


def get_current_user(session_id: str = Depends(get_session_id)) -> UserInfo:
    """每次认证读取当前用户状态，业务接口无需信任前端传入的用户 ID。"""
    try:
        return UserService().get_login_user(session_id)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from None
    except (RedisError, SQLAlchemyError):
        raise HTTPException(503, "登录服务暂不可用") from None
