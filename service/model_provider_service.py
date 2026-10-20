"""管理模型服务的连接配置，并在删除配置时清理所属模型。"""

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import model_dao, model_provider_dao
from dao.base_dao import BaseDao
from model.model_provider_info import (
    ModelProviderCreate, ModelProviderInfo, ModelProviderUpdate,
)


class ModelProviderService:
    def __init__(self, db: MySQLConnection | None = None):
        self.db = db if db is not None else get_mysql_connection()

    def list_providers(self) -> list[ModelProviderInfo]:
        with self.db.session() as session:
            return model_provider_dao.list_providers(session)

    def get(self, provider_id: int) -> ModelProviderInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, ModelProviderInfo, provider_id)

    def create(self, data: ModelProviderCreate) -> ModelProviderInfo:
        item = ModelProviderInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def update(self, provider_id: int, data: ModelProviderUpdate) -> ModelProviderInfo | None:
        with self.db.session() as session:
            item = BaseDao.get(session, ModelProviderInfo, provider_id)
            if item is None:
                return None
            values = data.model_dump(exclude={"api_key"})
            if data.api_key is not None:
                values["api_key"] = data.api_key
            return BaseDao.update(session, item, values)

    def delete(self, provider_id: int) -> bool:
        """服务配置和所属模型在同一事务中删除。"""
        with self.db.session() as session:
            item = BaseDao.get(session, ModelProviderInfo, provider_id)
            if item is None:
                return False
            model_dao.delete_by_provider(session, provider_id)
            BaseDao.delete(session, item)
            return True
