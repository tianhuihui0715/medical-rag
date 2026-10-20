"""权限用户关联业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from model.permission_user_info import PermissionUserCreate, PermissionUserInfo
from dao import permission_user_dao
from dao.base_dao import BaseDao


class PermissionUserService:
    """管理权限与用户之间的直接分配关系。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_items(
        self, permission_id: int | None = None, user_id: int | None = None,
    ) -> list[PermissionUserInfo]:
        with self.db.session() as session:
            return permission_user_dao.list_items(session, permission_id, user_id)

    def get(self, item_id: int) -> PermissionUserInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, PermissionUserInfo, item_id)

    def create(self, data: PermissionUserCreate) -> PermissionUserInfo:
        item = PermissionUserInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def delete(self, item_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, PermissionUserInfo, item_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
            return True
