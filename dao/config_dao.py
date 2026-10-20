"""配置的自定义查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.config_info import ConfigInfo


def list_configs(session: Session, category: str | None = None) -> list[ConfigInfo]:
    """可按分类筛选，按分类、配置键和主键排序。"""
    query = select(ConfigInfo).order_by(
        col(ConfigInfo.category), col(ConfigInfo.key), col(ConfigInfo.id)
    )
    if category is not None:
        query = query.where(col(ConfigInfo.category) == category)
    return list(session.exec(query).all())


def get_by_key(session: Session, key: str) -> ConfigInfo | None:
    """按配置键查询，未找到时返回 None。"""
    query = select(ConfigInfo).where(col(ConfigInfo.key) == key)
    return session.exec(query).first()
