"""字典业务层，协调数据操作并管理事务。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from common.config.config_cache import ConfigCache
from model.dict_info import DictCreate, DictInfo, DictUpdate
from dao import dict_dao
from dao.base_dao import BaseDao


class DictService:
    """管理按类型和父节点组织的字典项。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_items(self, dict_type: str, parent_id: int | None = None) -> list[DictInfo]:
        with self.db.session() as session:
            return dict_dao.list_items(session, dict_type, parent_id)

    def get(self, item_id: int) -> DictInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, DictInfo, item_id)

    def create(self, data: DictCreate) -> DictInfo:
        item = DictInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        # 字典项可能被多个配置引用，提交后统一清除该数据库的配置缓存。
        ConfigCache.clear(self.db)
        return item

    def update(self, item_id: int, data: DictUpdate) -> DictInfo | None:
        with self.db.session() as session:
            item = BaseDao.get(session, DictInfo, item_id)
            if item is None:
                return None
            BaseDao.update(session, item, data.model_dump())
        ConfigCache.clear(self.db)
        return item

    def delete(self, item_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, DictInfo, item_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
        ConfigCache.clear(self.db)
        return True
