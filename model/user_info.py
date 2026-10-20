"""用户表实体及请求、响应模型，对外响应不包含密码。"""

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from model.base_entity import BaseEntity


class UserFields(SQLModel):
    username: str = Field(sa_type=Text)
    nickname: str = Field(default="", sa_type=Text)
    email: str = Field(default="", sa_type=Text)
    enabled: bool = True


class UserCreate(UserFields):
    password: str = Field(sa_type=Text)


class UserUpdate(UserFields):
    # PUT 替换用户资料；不传密码则保留原密码。
    password: str | None = None


class UserInfo(UserCreate, BaseEntity, table=True):
    """用户的数据库实体，password 保存 Argon2 密码哈希。"""
    __tablename__ = "user_info"  # pyright: ignore[reportAssignmentType]


class UserRead(UserFields, BaseEntity):
    """对外响应中不包含密码。"""


class LoginRequest(SQLModel):
    username: str
    password: str


class LoginResult(SQLModel):
    """业务层登录结果；会话 ID 只用于设置 Cookie，不返回到响应正文。"""
    session_id: str
    expires_in: int
    user: UserRead
