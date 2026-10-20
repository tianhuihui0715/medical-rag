"""权限角色关联业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from model.permission_role_info import PermissionRoleCreate, PermissionRoleInfo
from dao import permission_role_dao
from dao.base_dao import BaseDao


class PermissionRoleService:
    """管理权限与角色之间的分配、查询和解除关系。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_items(
        self, permission_id: int | None = None, role_id: int | None = None,
    ) -> list[PermissionRoleInfo]:
        with self.db.session() as session:
            return permission_role_dao.list_items(session, permission_id, role_id)

    def get(self, item_id: int) -> PermissionRoleInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, PermissionRoleInfo, item_id)

    def create(self, data: PermissionRoleCreate) -> PermissionRoleInfo:
        item = PermissionRoleInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def delete(self, item_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, PermissionRoleInfo, item_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
            return True
