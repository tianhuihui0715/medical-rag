"""角色业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from model.role_info import RoleCreate, RoleInfo, RoleUpdate
from dao import file_role_dao
from dao import permission_role_dao
from dao import role_dao
from dao import user_role_dao
from dao.base_dao import BaseDao


class RoleService:
    """管理角色资料以及删除角色时的关联清理。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_roles(self) -> list[RoleInfo]:
        with self.db.session() as session:
            return role_dao.list_roles(session)

    def get(self, role_id: int) -> RoleInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, RoleInfo, role_id)

    def create(self, data: RoleCreate) -> RoleInfo:
        item = RoleInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def update(self, role_id: int, data: RoleUpdate) -> RoleInfo | None:
        """更新角色名称、描述和启用状态，保留角色编码。"""
        with self.db.session() as session:
            item = BaseDao.get(session, RoleInfo, role_id)
            if item is None:
                return None
            return BaseDao.update(session, item, data.model_dump())

    def delete(self, role_id: int) -> bool:
        """在同一事务中删除角色及其用户、权限和文件关联。"""
        with self.db.session() as session:
            item = BaseDao.get(session, RoleInfo, role_id)
            if item is None:
                return False
            user_role_dao.delete_by_role(session, role_id)
            permission_role_dao.delete_by_role(session, role_id)
            file_role_dao.delete_by_role(session, role_id)
            BaseDao.delete(session, item)
            return True
