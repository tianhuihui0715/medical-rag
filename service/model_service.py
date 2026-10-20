"""管理模型并调用模型服务，按数据库提示词改写问题及选择知识库。"""

import json
import logging
from typing import Any

import httpx
from langchain_core.messages import convert_to_openai_messages
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompt_values import PromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from clint.model_connection import ModelConnection, get_model_connection
from clint.mysql_connection import MySQLConnection, get_mysql_connection
from common.config.config import Config
from dao import knowledge_dao, model_dao
from dao.base_dao import BaseDao
from model.model_info import ModelCreate, ModelInfo, ModelUpdate
from model.model_provider_info import ModelProviderInfo
from service.config_service import ConfigService

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(
        self, db: MySQLConnection | None = None, connection: ModelConnection | None = None,
    ):
        self.db = db if db is not None else get_mysql_connection()
        self.connection = connection

    def list_models(
        self, provider_id: int | None = None, kind: str | None = None,
    ) -> list[ModelInfo]:
        with self.db.session() as session:
            return model_dao.list_models(session, provider_id, kind)

    def get(self, model_id: int) -> ModelInfo | None:
        with self.db.session() as session:
            return BaseDao.get(session, ModelInfo, model_id)

    def get_default(self, kind: str) -> ModelInfo | None:
        with self.db.session() as session:
            return model_dao.get_default(session, kind)

    def set_default(self, model_id: int) -> ModelInfo | None:
        """同一事务中取消同用途的旧选择，并选中当前模型。"""
        with self.db.session() as session:
            items = model_dao.list_for_update(session)
            item = next((item for item in items if item.id == model_id), None)
            if item is None:
                return None
            if item.kind not in ("chat", "embedding", "rerank"):
                raise ValueError("模型用途应为 chat、embedding 或 rerank")
            provider = BaseDao.get(session, ModelProviderInfo, item.provider_id)
            if provider is None or not item.enabled or not provider.enabled:
                raise ValueError("请选择模型和服务配置均已启用的模型")
            model_dao.clear_default(session, item.kind)
            return BaseDao.update(session, item, {"is_default": True})

    def create(self, data: ModelCreate) -> ModelInfo:
        item = ModelInfo.model_validate(data)
        with self.db.session() as session:
            BaseDao.add(session, item)
        return item

    def update(self, model_id: int, data: ModelUpdate) -> ModelInfo | None:
        with self.db.session() as session:
            item = BaseDao.get(session, ModelInfo, model_id)
            if item is None:
                return None
            values = data.model_dump()
            # 改变用途后需重新选择，避免与新用途已有的默认模型冲突。
            if data.kind != item.kind:
                values["is_default"] = False
            return BaseDao.update(session, item, values)

    def delete(self, model_id: int) -> bool:
        with self.db.session() as session:
            item = BaseDao.get(session, ModelInfo, model_id)
            if item is None:
                return False
            BaseDao.delete(session, item)
            return True

    def rewrite(self, query: str) -> str:
        """通过 LangChain 编排提示词、默认模型和文本输出，关闭或失败时返回原问题。"""
        if not query.strip():
            return query
        try:
            config = ConfigService(self.db)
            if not Config.to_bool(config.get_value("query_rewrite_enabled")):
                return query
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{instruction}"), ("human", "{query}"),
            ])

            chain = prompt | RunnableLambda(self.invoke_chat) | StrOutputParser()
            content = chain.invoke({
                "instruction": config.get_value("query_rewrite_prompt"), "query": query,
            })
            return content.strip() or query
        except (LookupError, ValueError, TypeError, RuntimeError, httpx.HTTPError) as exc:
            logger.warning("问题改写失败，使用原问题：%s", exc)
            return query

    def select_knowledge(self, query: str, user_id: int) -> list[int]:
        """将改写后的问题匹配到授权知识库；无匹配或模型调用失败时返回空列表。"""
        if not query.strip():
            return []
        with self.db.session() as session:
            candidates = knowledge_dao.list_accessible(session, user_id)
        if not candidates:
            return []
        # 只提供路由所需资料，模型推理在数据库事务结束后执行。
        knowledge = [
            {"id": item.id, "name": item.name, "description": item.description}
            for item in candidates
        ]
        try:
            config = ConfigService(self.db)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{instruction}"),
                ("human", "候选知识库（JSON）：\n{knowledge}\n\n改写后的问题：\n{query}"),
            ])
            chain = prompt | RunnableLambda(self.invoke_chat) | JsonOutputParser()
            result = chain.invoke({
                "instruction": config.get_value("knowledge_route_prompt"),
                "knowledge": json.dumps(knowledge, ensure_ascii=False), "query": query,
            })
            if not isinstance(result, dict) or not isinstance(result.get("knowledge_ids"), list):
                raise ValueError("知识库路由结果缺少 knowledge_ids 数组")
            allowed = {item.id for item in candidates}
            # 模型只能缩小候选范围，不能授予权限；保持输出顺序并去重。
            return list(dict.fromkeys(
                item for item in result["knowledge_ids"] if type(item) is int and item in allowed
            ))
        except (LookupError, ValueError, TypeError, RuntimeError, httpx.HTTPError) as exc:
            logger.warning("知识库选择失败，本次不检索：%s", exc)
            return []

    def invoke_chat(self, value: PromptValue, model_id: int | None = None) -> str:
        """将 LangChain 提示词交给聊天模型，返回正文，供改写和后续生成链复用。"""
        result = self.call(model_id, "chat", {
            "messages": convert_to_openai_messages(value.to_messages()),
        })
        return result["choices"][0]["message"]["content"]

    def call(self, model_id: int | None, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """未指定 ID 时使用该用途的默认模型；网络调用在数据库事务外执行。"""
        paths = {"chat": "chat/completions", "embedding": "embeddings", "rerank": "rerank"}
        with self.db.session() as session:
            item = (
                BaseDao.get(session, ModelInfo, model_id)
                if model_id is not None else model_dao.get_default(session, kind)
            )
            if item is None:
                raise LookupError("模型不存在" if model_id is not None else "该用途尚未选择默认模型")
            provider = BaseDao.get(session, ModelProviderInfo, item.provider_id)
            if provider is None:
                raise LookupError("模型服务配置不存在")
            if kind not in paths or item.kind != kind:
                raise ValueError("模型用途与调用接口不匹配")
            if not item.enabled or not provider.enabled:
                raise ValueError("模型或服务配置已停用")
        # 远程推理不占用数据库连接；输入及模型名称优先于保存的默认参数。
        payload = {**item.params, **inputs, "model": item.name}
        if kind == "chat":
            payload["stream"] = False
        connection = self.connection if self.connection is not None else get_model_connection()
        return connection.call(provider, item.api_path or paths[kind], payload)
