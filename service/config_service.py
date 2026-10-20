"""配置业务层，协调数据操作并管理事务。"""

from sqlalchemy.exc import IntegrityError

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from common.config.config_cache import ConfigCache
from model.config_info import ConfigCreate, ConfigInfo, ConfigUpdate
from service.dict_service import DictService
from dao import config_dao
from dao.base_dao import BaseDao


class ConfigService:
    """管理配置数据，并将字典类型配置解析为值列表。"""
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_configs(self, category: str | None = None) -> list[ConfigInfo]:
        with self.db.session() as session:
            return config_dao.list_configs(session, category)

    def get(self, config_id: int) -> ConfigInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, ConfigInfo, config_id)

    def get_by_key(self, key: str) -> ConfigInfo | None:
        with self.db.session() as session:
            return config_dao.get_by_key(session, key)

    def get_value(self, key: str) -> str | list[str]:
        """业务取值复用跨请求缓存，管理接口的列表和详情仍直接查询数据库。"""
        return ConfigCache.get(self.db, key, lambda: self._load_value(key))

    def _load_value(self, key: str) -> str | list[str]:
        """普通配置返回字符串；字典配置按其值指定的类型读取根字典项。"""
        item = self.get_by_key(key)
        if item is None:
            raise LookupError(f"配置不存在：{key}")
        if item.use_dict:
            return [row.value for row in DictService(self.db).list_items(item.value)]
        return item.value

    def create(self, data: ConfigCreate) -> ConfigInfo:
        """新增配置，重复键转换为业务层的 FileExistsError。"""
        item = ConfigInfo.model_validate(data)
        try:
            with self.db.session() as session:
                BaseDao.add(session, item)
        except IntegrityError:
            raise FileExistsError("配置键已存在") from None
        ConfigCache.clear(self.db)
        return item

    def update(self, config_id: int, data: ConfigUpdate) -> ConfigInfo | None:
        with self.db.session() as session:
            item = BaseDao.get(session, ConfigInfo, config_id)
            if item is None:
                return None
            BaseDao.update(session, item, data.model_dump())
        ConfigCache.clear(self.db)
        return item

    def delete(self, config_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, ConfigInfo, config_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
        ConfigCache.clear(self.db)
        return True
