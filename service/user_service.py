"""管理用户、密码哈希及 Redis 登录会话，协调数据库事务。"""

import hashlib
import secrets
from typing import cast

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from clint.redis_connection import RedisConnection, get_redis_connection
from model.user_info import LoginResult, UserCreate, UserInfo, UserRead, UserUpdate
from dao import permission_user_dao
from dao import user_dao
from dao import user_role_dao
from dao.base_dao import BaseDao
from service.config_service import ConfigService

_password_hasher = PasswordHasher()


class UserService:
    """管理用户资料、登录会话以及删除用户时的关联清理。"""
    def __init__(self, db: MySQLConnection | None = None, redis: RedisConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()
        self.redis = redis if redis is not None else get_redis_connection()

    def list_users(self) -> list[UserInfo]:
        with self.db.session() as session:
            return user_dao.list_users(session)

    def get(self, user_id: int) -> UserInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, UserInfo, user_id)

    def create(self, data: UserCreate) -> UserInfo:
        item = UserInfo.model_validate(data)
        # 密码计算在事务外执行，数据库只保存哈希。
        item.password = _password_hasher.hash(data.password)
        with self.db.session() as session:
            if user_dao.get_by_username(session, data.username) is not None:
                raise FileExistsError("用户名已存在")
            BaseDao.add(session, item)
        return item

    def update(self, user_id: int, data: UserUpdate) -> UserInfo | None:
        """更新用户资料；密码未传或为 None 时保留原密码。"""
        values = data.model_dump(exclude={"password"})
        if data.password is not None:
            values["password"] = _password_hasher.hash(data.password)
        with self.db.session() as session:
            item = BaseDao.get(session, UserInfo, user_id)
            if item is None:
                return None
            existing = user_dao.get_by_username(session, data.username)
            if existing is not None and existing.id != user_id:
                raise FileExistsError("用户名已存在")
            return BaseDao.update(session, item, values)

    def login(self, username: str, password: str) -> LoginResult:
        """验证密码后生成随机会话 ID，Redis 保存其摘要、用户 ID 及有效期。"""
        with self.db.session() as session:
            item = user_dao.get_by_username(session, username)
        if item is None or not item.enabled:
            raise PermissionError("用户名或密码错误")
        try:
            _password_hasher.verify(item.password, password)
        except (InvalidHashError, VerificationError):
            raise PermissionError("用户名或密码错误") from None
        expires = int(cast(str, ConfigService(self.db).get_value("login_expire_seconds")))
        session_id = secrets.token_urlsafe(32)
        self.redis.client.set(self._session_key(session_id), cast(int, item.id), ex=expires)
        return LoginResult(
            session_id=session_id, expires_in=expires, user=UserRead.model_validate(item),
        )

    def get_login_user(self, session_id: str) -> UserInfo:
        """从会话获取身份并读取最新用户状态，过期、禁用或删除均不能继续认证。"""
        user_id = self.redis.client.get(self._session_key(session_id))
        if user_id is None:
            raise PermissionError("登录已失效，请重新登录")
        with self.db.session() as session:
            item = BaseDao.get(session, UserInfo, int(cast(bytes | str, user_id)))
        if item is None or not item.enabled or item.is_deleted:
            raise PermissionError("登录已失效，请重新登录")
        return item

    def logout(self, session_id: str) -> None:
        self.redis.client.delete(self._session_key(session_id))

    @staticmethod
    def _session_key(session_id: str) -> str:
        return "auth:session:" + hashlib.sha256(session_id.encode()).hexdigest()

    def delete(self, user_id: int) -> bool:
        """在同一事务中删除用户及其角色、直接权限关联。"""
        with self.db.session() as session:
            item = BaseDao.get(session, UserInfo, user_id)
            if item is None:
                return False
            user_role_dao.delete_by_user(session, user_id)
            permission_user_dao.delete_by_user(session, user_id)
            BaseDao.delete(session, item)
            return True
