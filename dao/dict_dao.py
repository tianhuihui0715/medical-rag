"""字典的自定义查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.dict_info import DictInfo


def list_items(
    session: Session, dict_type: str, parent_id: int | None = None,
) -> list[DictInfo]:
    """查询指定类型的同级字典项；parent_id 为 None 时查询根节点。"""
    query = (
        select(DictInfo)
        .where(
            col(DictInfo.dict_type) == dict_type,
            col(DictInfo.parent_id) == parent_id,
        )
        .order_by(col(DictInfo.id))
    )
    return list(session.exec(query).all())
