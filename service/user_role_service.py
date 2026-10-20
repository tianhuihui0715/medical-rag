"""用户角色关联业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from model.user_role_info import UserRoleCreate, UserRoleInfo
from dao import user_role_dao
from dao.base_dao import BaseDao


class UserRoleService:
    """管理用户与角色之间的分配、查询和解除关系。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_items(
        self, user_id: int | None = None, role_id: int | None = None,
    ) -> list[UserRoleInfo]:
        with self.db.session() as session:
            return user_role_dao.list_items(session, user_id, role_id)

    def get(self, item_id: int) -> UserRoleInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, UserRoleInfo, item_id)

    def create(self, data: UserRoleCreate) -> UserRoleInfo:
        item = UserRoleInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def delete(self, item_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, UserRoleInfo, item_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
            return True
