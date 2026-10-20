"""模型条件查询及删除服务配置时的模型清理语句。"""

from sqlalchemy import delete, update
from sqlmodel import Session, col, select

from model.model_info import ModelInfo


def list_models(
    session: Session, provider_id: int | None = None, kind: str | None = None,
) -> list[ModelInfo]:
    query = select(ModelInfo).order_by(col(ModelInfo.id))
    if provider_id is not None:
        query = query.where(col(ModelInfo.provider_id) == provider_id)
    if kind is not None:
        query = query.where(col(ModelInfo.kind) == kind)
    return list(session.exec(query).all())


def delete_by_provider(session: Session, provider_id: int) -> None:
    session.exec(delete(ModelInfo).where(col(ModelInfo.provider_id) == provider_id))


def get_default(session: Session, kind: str) -> ModelInfo | None:
    """读取当前用途的系统默认模型；启用状态由业务调用时判断。"""
    query = select(ModelInfo).where(
        col(ModelInfo.kind) == kind, col(ModelInfo.is_default).is_(True),
    )
    return session.exec(query).first()


def list_for_update(session: Session) -> list[ModelInfo]:
    """按主键顺序锁定模型配置，使并发切换默认模型时串行处理。"""
    query = select(ModelInfo).order_by(col(ModelInfo.id)).with_for_update()
    return list(session.exec(query).all())


def clear_default(session: Session, kind: str) -> None:
    session.exec(
        update(ModelInfo).where(col(ModelInfo.kind) == kind).values(is_default=False)
    )
