"""权限业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from model.permission_info import PermissionCreate, PermissionInfo, PermissionUpdate
from dao import permission_dao
from dao import permission_role_dao
from dao import permission_user_dao
from dao.base_dao import BaseDao


class PermissionService:
    """管理权限资料以及删除权限时的关联清理。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_permissions(self) -> list[PermissionInfo]:
        with self.db.session() as session:
            return permission_dao.list_permissions(session)

    def get(self, permission_id: int) -> PermissionInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, PermissionInfo, permission_id)

    def create(self, data: PermissionCreate) -> PermissionInfo:
        item = PermissionInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def update(self, permission_id: int, data: PermissionUpdate) -> PermissionInfo | None:
        """更新权限名称、描述和启用状态，保留权限编码。"""
        with self.db.session() as session:
            item = BaseDao.get(session, PermissionInfo, permission_id)
            if item is None:
                return None
            return BaseDao.update(session, item, data.model_dump())

    def delete(self, permission_id: int) -> bool:
        """在同一事务中删除权限及其角色、用户关联。"""
        with self.db.session() as session:
            item = BaseDao.get(session, PermissionInfo, permission_id)
            if item is None:
                return False
            permission_role_dao.delete_by_permission(session, permission_id)
            permission_user_dao.delete_by_permission(session, permission_id)
            BaseDao.delete(session, item)
            return True
