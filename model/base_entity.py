"""定义实体公共字段，包括主键、删除标记、创建信息和更新信息。"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """生成带 UTC 时区的时间，供审计字段使用。"""
    return datetime.now(timezone.utc)


class BaseEntity(SQLModel):
    """各数据表共用的主键及审计字段。"""
    id: int | None = Field(default=None, primary_key=True)
    is_deleted: int = 0
    created_by: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_by: int | None = Field(default=None)
    updated_at: datetime = Field(
        default_factory=utc_now, nullable=False, sa_column_kwargs={"onupdate": utc_now}
    )
