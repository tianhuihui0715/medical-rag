"""查询授权知识库，并处理上传时的默认知识库和文件关联。"""

from sqlmodel import Session, col, select

from dao import file_dao
from dao.base_dao import BaseDao
from model.file_info import FileInfo
from model.knowledge_base_info import KnowledgeBaseInfo
from model.knowledge_file_info import KnowledgeFileInfo


def get_for_upload(session: Session, knowledge_id: int | None) -> KnowledgeBaseInfo:
    """锁定上传目标；未指定时按名称复用或创建默认知识库。"""
    query = select(KnowledgeBaseInfo).where(col(KnowledgeBaseInfo.is_deleted) == 0)
    if knowledge_id is not None:
        item = session.exec(query.where(col(KnowledgeBaseInfo.id) == knowledge_id).with_for_update()).first()
        if item is None:
            raise FileNotFoundError("知识库不存在")
        return item
    item = session.exec(query.where(
        col(KnowledgeBaseInfo.name) == "默认知识库",
    ).order_by(col(KnowledgeBaseInfo.id)).with_for_update()).first()
    if item is None:
        item = BaseDao.add(session, KnowledgeBaseInfo(
            name="默认知识库", description="保存上传时未指定知识库的文件。",
        ))
    return item


def add_files(session: Session, knowledge_id: int, file_ids: list[int]) -> None:
    """调用方持有知识库行锁，在同一事务中补齐关联，跳过已有及同批重复文件。"""
    file_ids = list(dict.fromkeys(file_ids))
    if not file_ids:
        return
    existing = set(session.exec(select(KnowledgeFileInfo.file_id).where(
        col(KnowledgeFileInfo.knowledge_id) == knowledge_id,
        col(KnowledgeFileInfo.file_id).in_(file_ids), col(KnowledgeFileInfo.is_deleted) == 0,
    )).all())
    BaseDao.add_many(session, [
        KnowledgeFileInfo(knowledge_id=knowledge_id, file_id=file_id)
        for file_id in file_ids if file_id not in existing
    ])


def list_accessible(
    session: Session, user_id: int, source_path: str | None = None,
) -> list[KnowledgeBaseInfo]:
    """沿用文件角色权限，排除空库、停用库及已删除的关联；查询在一条 SQL 中完成。"""
    files = file_dao.accessible_query(user_id, source_path).with_only_columns(col(FileInfo.id)).order_by(None)
    knowledge = select(KnowledgeFileInfo.knowledge_id).where(
        col(KnowledgeFileInfo.file_id).in_(files), col(KnowledgeFileInfo.is_deleted) == 0,
    )
    query = select(KnowledgeBaseInfo).where(
        col(KnowledgeBaseInfo.id).in_(knowledge),
        col(KnowledgeBaseInfo.enabled).is_(True), col(KnowledgeBaseInfo.is_deleted) == 0,
    ).order_by(col(KnowledgeBaseInfo.id))
    return list(session.exec(query).all())


def list_files(
    session: Session, user_id: int, knowledge_ids: list[int], source_path: str | None = None,
) -> list[FileInfo]:
    """将指定知识库范围与最新文件权限取交集，停用库和已删除关联不参与检索。"""
    if not knowledge_ids:
        return []
    files = select(KnowledgeFileInfo.file_id).join(
        KnowledgeBaseInfo, col(KnowledgeBaseInfo.id) == col(KnowledgeFileInfo.knowledge_id),
    ).where(
        col(KnowledgeFileInfo.knowledge_id).in_(knowledge_ids),
        col(KnowledgeFileInfo.is_deleted) == 0,
        col(KnowledgeBaseInfo.enabled).is_(True), col(KnowledgeBaseInfo.is_deleted) == 0,
    )
    return list(session.exec(
        file_dao.accessible_query(user_id, source_path).where(col(FileInfo.id).in_(files)),
    ).all())
