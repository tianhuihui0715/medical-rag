"""读取子块，批量生成稠密及可选稀疏向量，并将文件角色信息一起保存到 Milvus。"""

import logging
import math
from typing import Any, cast

from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import chunk_dao, file_dao, file_role_dao
from dao.base_dao import BaseDao
from dao.vector_dao import VectorDao
from model.file_info import FileInfo
from service.config_service import ConfigService
from service.model_service import ModelService

logger = logging.getLogger(__name__)


class IngestService:
    """子块入向量库，父块用于后续命中回溯；推理和 Milvus 调用均不占用 SQL 事务。"""
    def __init__(
        self, db: MySQLConnection | None = None, models: ModelService | None = None,
        vectors: VectorDao | None = None,
    ):
        self.db = db if db is not None else get_mysql_connection()
        self.models = models if models is not None else ModelService(self.db)
        self.vectors = vectors
        config = ConfigService(self.db)
        self.batch_size = int(cast(str, config.get_value("embedding_batch_size")))
        self.collection_prefix = cast(str, config.get_value("vector_collection_prefix"))
        if self.batch_size <= 0:
            raise ValueError("embedding_batch_size 必须大于 0")

    def ingest_file(self, file_id: int, model_id: int | None = None) -> dict[str, Any]:
        """领取文件后批量重建向量；失败清理本次文件数据并记录状态，支持再次执行。"""
        if model_id is None:
            model = self.models.get_default("embedding")
            if model is None:
                raise LookupError("尚未选择默认向量模型")
            model_id = cast(int, model.id)
        collection = f"{self.collection_prefix}_{model_id}"
        with self.db.session() as session:
            item = file_dao.get_for_update(session, file_id)
            if item is None:
                raise FileNotFoundError("文件不存在")
            if item.parse_status != "completed" or item.split_status != "completed":
                raise ValueError("请先完成文件解析和切块")
            if item.ingest_status == "processing":
                raise FileExistsError("文件正在向量入库")
            children = chunk_dao.list_children(session, file_id)
            roles = sorted({role.role_id for role in file_role_dao.list_items(session, file_id=file_id)})
            BaseDao.update(session, item, {"ingest_status": "processing", "error": ""})

        vectors = self.vectors
        rebuilding = False
        dimension: int | None = None
        has_sparse: bool | None = None
        try:
            vectors = vectors if vectors is not None else VectorDao()
            for start in range(0, len(children), self.batch_size):
                batch = children[start:start + self.batch_size]
                # 标题路径加入模型输入；表格和代码的上下文不依赖正文是否重复带标题。
                texts = [
                    "\n".join(child.meta.get("section", [])) + "\n\n" + child.content
                    if child.meta.get("section") else child.content
                    for child in batch
                ]
                result = self.models.call(model_id, "embedding", {"input": texts, "encoding_format": "float"})
                embeddings, sparse_vectors = self._read_vectors(result, len(batch), dimension, has_sparse)
                if dimension is None:
                    dimension = len(embeddings[0])
                    has_sparse = sparse_vectors is not None
                    if has_sparse:
                        # 双向量使用独立集合，不覆盖既有的纯稠密集合结构。
                        collection += "_hybrid"
                    vectors.ensure_collection(collection, dimension, sparse=has_sparse)
                    # 先确认推理与集合均可用，再清理旧向量；后续失败时删除本次部分写入。
                    rebuilding = True
                    vectors.delete_file(collection, file_id)
                rows = []
                for index, (child, embedding) in enumerate(zip(batch, embeddings)):
                    row = {
                        "id": child.id, "file_id": file_id, "parent_id": child.parent_id,
                        "model_id": model_id, "role_ids": roles, "vector": embedding,
                    }
                    if sparse_vectors is not None:
                        row["sparse_vector"] = sparse_vectors[index]
                    rows.append(row)
                vectors.write_vectors(collection, rows)
            if not children:
                # 空文档重切后也清除已有的派生向量。
                if item.embedding_model_id == model_id and item.vector_collection:
                    collection = item.vector_collection
                    has_sparse = collection.endswith("_hybrid")
                rebuilding = True
                vectors.delete_file(collection, file_id)
            with self.db.session() as session:
                current = BaseDao.get(session, FileInfo, file_id)
                if current is None:
                    raise FileNotFoundError("文件不存在")
                BaseDao.update(session, current, {
                    "ingest_status": "completed", "embedding_model_id": model_id,
                    "vector_collection": collection, "error": "",
                })
            if item.vector_collection and item.vector_collection != collection:
                try:
                    vectors.delete_file(item.vector_collection, file_id)
                except Exception:
                    logger.exception("新向量已保存，清理文件旧集合数据失败，file_id=%s", file_id)
            return {
                "ingest_status": "completed", "embedding_model_id": model_id,
                "vector_collection": collection, "vector_count": len(children),
                "has_sparse": bool(has_sparse),
            }
        except Exception as exc:
            if rebuilding and vectors is not None:
                try:
                    vectors.delete_file(collection, file_id)
                except Exception:
                    logger.exception("清理文件部分向量失败，file_id=%s", file_id)
            try:
                with self.db.session() as session:
                    current = BaseDao.get(session, FileInfo, file_id)
                    if current is not None:
                        BaseDao.update(session, current, {"ingest_status": "failed", "error": str(exc)})
            except Exception:
                logger.exception("记录文件向量入库失败状态时发生错误，file_id=%s", file_id)
            raise

    @staticmethod
    def _read_vectors(
        result: dict[str, Any], count: int, dimension: int | None, has_sparse: bool | None = None,
    ) -> tuple[list[list[float]], list[dict[int, float]] | None]:
        """按 index 对齐双向量；同一文件各批次须保持一致，避免漏存稀疏数据。"""
        rows = sorted(result.get("data", []), key=lambda row: row["index"])
        if [row["index"] for row in rows] != list(range(count)):
            raise RuntimeError("向量模型返回条数或索引与输入不匹配")
        embeddings = [row["embedding"] for row in rows]
        size = dimension if dimension is not None else len(embeddings[0])
        if not size or any(
            len(embedding) != size or not all(math.isfinite(value) for value in embedding)
            for embedding in embeddings
        ):
            raise RuntimeError("向量模型返回了无效向量或不一致的维度")
        sparse_flags = ["sparse_embedding" in row for row in rows]
        present = all(sparse_flags)
        if any(sparse_flags) != present or (has_sparse is not None and present != has_sparse):
            raise RuntimeError("向量模型返回的稀疏向量不完整或各批次格式不一致")
        if not present:
            return embeddings, None
        try:
            sparse_vectors = [
                {int(token): float(weight) for token, weight in row["sparse_embedding"].items()}
                for row in rows
            ]
        except (AttributeError, TypeError, ValueError):
            raise RuntimeError("向量模型返回了无效的稀疏向量") from None
        if any(
            token < 0 or not math.isfinite(weight)
            for vector in sparse_vectors for token, weight in vector.items()
        ):
            raise RuntimeError("向量模型返回了无效的稀疏向量")
        return embeddings, sparse_vectors
