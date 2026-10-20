"""查询文件内容哈希及用户授权范围，批量保存文件元数据。"""

from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from dao.base_dao import BaseDao
from model.file_info import FileInfo
from model.file_role_info import FileRoleInfo
from model.role_info import RoleInfo
from model.user_info import UserInfo
from model.user_role_info import UserRoleInfo


def accessible_query(user_id: int, source_path: str | None = None) -> SelectOfScalar[FileInfo]:
    """构造当前用户可检索文件的查询，供文件列表及知识库路由复用。"""
    roles = select(UserRoleInfo.role_id).join(
        RoleInfo, col(RoleInfo.id) == col(UserRoleInfo.role_id),
    ).join(
        UserInfo, col(UserInfo.id) == col(UserRoleInfo.user_id),
    ).where(
        col(UserInfo.id) == user_id, col(UserInfo.enabled).is_(True), col(UserInfo.is_deleted) == 0,
        col(RoleInfo.enabled).is_(True), col(RoleInfo.is_deleted) == 0,
        col(UserRoleInfo.is_deleted) == 0,
    )
    grants = select(FileRoleInfo.file_id).where(
        col(FileRoleInfo.role_id).in_(roles), col(FileRoleInfo.is_deleted) == 0,
    )
    # 子查询在同一条 SQL 中执行，多角色命中同一文件也只返回一次。
    query = select(FileInfo).where(
        col(FileInfo.id).in_(grants), col(FileInfo.is_deleted) == 0,
        col(FileInfo.parse_status) == "completed", col(FileInfo.split_status) == "completed",
        col(FileInfo.ingest_status) == "completed",
    ).order_by(col(FileInfo.id))
    if source_path is not None:
        # 前缀包含目录分隔符，且转义 LIKE 通配符，避免匹配相似目录名。
        query = query.where(col(FileInfo.source_path).startswith(source_path, autoescape=True))
    return query


def list_accessible(
    session: Session, user_id: int, file_ids: list[int] | None = None,
) -> list[FileInfo]:
    """按最新有效授权查询可检索文件；指定文件范围时取交集，空范围不返回任何文件。"""
    if file_ids is not None and not file_ids:
        return []
    query = accessible_query(user_id)
    if file_ids is not None:
        query = query.where(col(FileInfo.id).in_(file_ids))
    return list(session.exec(query).all())


def get_for_update(session: Session, file_id: int) -> FileInfo | None:
    """锁定文件记录，供解析、切块任务互斥领取及更新结果。"""
    query = select(FileInfo).where(col(FileInfo.id) == file_id).with_for_update()
    return session.exec(query).first()


def get_by_ids(session: Session, file_ids: list[int]) -> dict[int, FileInfo]:
    """一次查询本批文件，按 ID 关联，调用方处理不存在的记录。"""
    if not file_ids:
        return {}
    rows = session.exec(select(FileInfo).where(col(FileInfo.id).in_(file_ids))).all()
    return {item.id: item for item in rows if item.id is not None}


def get_by_hashes(session: Session, hashes: list[str]) -> dict[tuple[str, int], FileInfo]:
    """查询未删除的相同内容文件，以哈希和大小关联结果。"""
    if not hashes:
        return {}
    query = select(FileInfo).where(
        col(FileInfo.content_hash).in_(hashes), col(FileInfo.is_deleted) == 0,
    )
    return {
        (item.content_hash, item.size): item
        for item in session.exec(query).all()
        if item.content_hash is not None
    }


def add_many(session: Session, items: list[FileInfo]) -> list[FileInfo]:
    """同一事务中批量插入并查询结果，返回顺序与输入一致。"""
    if not items:
        return []
    BaseDao.add_many(session, items)
    # MySQL 批量 INSERT 不返回每条自增 ID，使用本次生成的 UUID 对象名关联结果。
    names = [item.object_name for item in items]
    rows = session.exec(select(FileInfo).where(col(FileInfo.object_name).in_(names))).all()
    by_name = {item.object_name: item for item in rows}
    return [by_name[name] for name in names]
