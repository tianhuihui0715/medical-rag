"""在调用方事务中替换文件的父子块，统一维护父块 ID 关联。"""

from sqlmodel import Session, col, delete, select

from dao.base_dao import BaseDao
from model.chunk_info import ChunkInfo


def list_children(session: Session, file_id: int) -> list[ChunkInfo]:
    """仅查询当前文件未删除的子块，按切块顺序作为模型批量输入。"""
    query = select(ChunkInfo).where(
        col(ChunkInfo.file_id) == file_id,
        col(ChunkInfo.parent_id).is_not(None), col(ChunkInfo.is_deleted) == 0,
    ).order_by(col(ChunkInfo.chunk_index))
    return list(session.exec(query).all())


def list_parents(session: Session, parent_ids: list[int], file_ids: list[int]) -> list[ChunkInfo]:
    """批量回溯授权文件的有效父块，过滤重切后已失效的向量命中。"""
    if not parent_ids or not file_ids:
        return []
    query = select(ChunkInfo).where(
        col(ChunkInfo.id).in_(parent_ids), col(ChunkInfo.file_id).in_(file_ids),
        col(ChunkInfo.parent_id).is_(None), col(ChunkInfo.is_deleted) == 0,
    )
    return list(session.exec(query).all())


def replace(
    session: Session, file_id: int, groups: list[tuple[ChunkInfo, list[ChunkInfo]]],
) -> None:
    """删除旧块、生成父块 ID 后批量保存子块；异常由会话统一回滚。"""
    session.exec(delete(ChunkInfo).where(col(ChunkInfo.file_id) == file_id))
    session.add_all([parent for parent, _ in groups])
    session.flush()
    children: list[ChunkInfo] = []
    for parent, items in groups:
        for child in items:
            child.parent_id = parent.id
        children.extend(items)
    BaseDao.add_many(session, children)
