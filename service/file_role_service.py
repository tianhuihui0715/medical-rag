"""文件角色关联业务，管理文件授权及解除授权的事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import file_role_dao
from dao.base_dao import BaseDao
from model.file_role_info import FileRoleCreate, FileRoleInfo


class FileRoleService:
    """管理文件与允许访问该文件的角色之间的关联。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_items(
        self, file_id: int | None = None, role_id: int | None = None,
    ) -> list[FileRoleInfo]:
        with self.db.session() as session:
            return file_role_dao.list_items(session, file_id, role_id)

    def get(self, item_id: int) -> FileRoleInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, FileRoleInfo, item_id)

    def create(self, data: FileRoleCreate) -> FileRoleInfo:
        item = FileRoleInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def delete(self, item_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, FileRoleInfo, item_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
            return True
