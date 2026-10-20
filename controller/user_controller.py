"""用户管理及 Cookie 登录接口，登录和退出同步维护浏览器与 Redis 会话。"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from common.auth import SESSION_COOKIE, get_current_user
from model.user_info import LoginRequest, UserCreate, UserInfo, UserRead, UserUpdate
from service.user_service import UserService

router = APIRouter(prefix="/user", tags=["用户"])


def get_service() -> UserService:
    return UserService()


@router.post("/login", response_model=UserRead, summary="用户名密码登录并设置会话 Cookie")
def login(
    data: LoginRequest, request: Request, response: Response,
    service: UserService = Depends(get_service),
):
    try:
        result = service.login(data.username, data.password)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from None
    except (RedisError, SQLAlchemyError):
        raise HTTPException(503, "登录服务暂不可用") from None
    response.set_cookie(
        SESSION_COOKIE, result.session_id, max_age=result.expires_in,
        httponly=True, secure=request.url.scheme == "https", samesite="lax", path="/",
    )
    return result.user


@router.get("/me", response_model=UserRead, summary="获取当前登录用户")
def get_me(user: UserInfo = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204, summary="退出当前登录")
def logout(request: Request, service: UserService = Depends(get_service)):
    session_id = request.cookies.get(SESSION_COOKIE)
    try:
        if session_id:
            service.logout(session_id)
    except RedisError:
        raise HTTPException(503, "登录服务暂不可用") from None
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True,
        secure=request.url.scheme == "https", samesite="lax",
    )
    return response


@router.get("", response_model=list[UserRead], summary="查询用户列表")
def list_users(service: UserService = Depends(get_service)):
    return service.list_users()


@router.get("/{user_id}", response_model=UserRead, summary="查询用户")
def get_user(user_id: int, service: UserService = Depends(get_service)):
    item = service.get(user_id)
    if item is None:
        raise HTTPException(404, "用户不存在")
    return item


@router.post("", response_model=UserRead, status_code=201, summary="新增用户")
def create_user(data: UserCreate, service: UserService = Depends(get_service)):
    try:
        return service.create(data)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from None


@router.put("/{user_id}", response_model=UserRead, summary="修改用户")
def update_user(
    user_id: int, data: UserUpdate, service: UserService = Depends(get_service)
):
    try:
        item = service.update(user_id, data)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from None
    if item is None:
        raise HTTPException(404, "用户不存在")
    return item


@router.delete("/{user_id}", status_code=204, summary="删除用户及角色关联")
def delete_user(user_id: int, service: UserService = Depends(get_service)):
    if not service.delete(user_id):
        raise HTTPException(404, "用户不存在")
    return Response(status_code=204)
