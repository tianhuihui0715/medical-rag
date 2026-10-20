"""通用数据访问基类，使用调用方传入的 Session 执行增删改查。"""

from typing import Any, TypeVar

from sqlalchemy import insert
from sqlmodel import Session, SQLModel

T = TypeVar("T", bound=SQLModel)


class BaseDao:
    """通用数据库操作，由调用方的会话上下文统一提交或回滚。"""

    @staticmethod
    def add(session: Session, item: T) -> T:
        """加入会话并刷新到数据库以获取主键，不提交事务。"""
        session.add(item)
        session.flush()
        return item

    @staticmethod
    def add_many(session: Session, items: list[T]) -> None:
        """批量执行 INSERT，不回填实体主键，提交和回滚由会话上下文处理。"""
        if items:
            session.execute(
                insert(type(items[0])),
                [item.model_dump(exclude={"id"}) for item in items],
            )

    @staticmethod
    def get(session: Session, model: type[T], item_id: int) -> T | None:
        """按主键查询，记录不存在时返回 None。"""
        return session.get(model, item_id)

    @staticmethod
    def update(session: Session, item: T, data: dict[str, Any]) -> T:
        """更新传入字典中的字段并刷新，不提交事务。"""
        for key, value in data.items():
            setattr(item, key, value)
        return BaseDao.add(session, item)

    @staticmethod
    def delete(session: Session, item: SQLModel) -> None:
        """标记实体为待删除，由调用方提交事务。"""
        session.delete(item)
