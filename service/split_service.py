"""合并切块参数、提交任务，读取解析结果并在独立事务中保存父子块。"""

import hashlib
import json
import logging
from typing import Any, cast

from langchain_core.documents import Document
from redis.exceptions import RedisError

from clint.minio_connection import MinIOConnection, get_minio_connection
from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import chunk_dao, file_dao
from dao.base_dao import BaseDao
from model.chunk_info import ChunkInfo, SplitOptions
from model.file_info import FileInfo
from service.config_service import ConfigService
from service.ingest_service import IngestService
from service.model_service import ModelService
from splitter.file_splitter import FileSplitter
from task.parse_queue import ParseQueue

logger = logging.getLogger(__name__)


class SplitService:
    """管理切块提交和父子块保存，由任务入口继续执行向量入库。"""
    def __init__(
        self, db: MySQLConnection | None = None,
        minio: MinIOConnection | None = None, queue: ParseQueue | None = None,
    ):
        self.db = db if db is not None else get_mysql_connection()
        self.minio = minio if minio is not None else get_minio_connection()
        self.queue = queue
        self.config = ConfigService(self.db)

    def start_split(self, file_ids: list[int], options: SplitOptions | None = None) -> list[dict[str, Any]]:
        """一批文件共用参数快照；每个文件独立入队并返回提交结果。"""
        file_ids = list(dict.fromkeys(file_ids))
        if not file_ids:
            return []
        with self.db.session() as session:
            items = file_dao.get_by_ids(session, file_ids)
        options = options if options is not None else SplitOptions()
        params = {
            name: value if value is not None else int(cast(str, self.config.get_value(f"chunk_{name}")))
            for name, value in options.model_dump(include={"parent_size", "child_size", "overlap"}).items()
        }
        model = ModelService(self.db).get_default("embedding")
        if model is None:
            raise LookupError("尚未选择默认向量模型")
        queue = self.queue
        results: list[dict[str, Any]] = []
        for file_id in file_ids:
            try:
                item = self._check(items.get(file_id))
                FileSplitter(item.extension, **params)
                queue = queue if queue is not None else ParseQueue()
                task_id = queue.enqueue(run_split_task, file_id, embedding_model_id=model.id, **params)
            except (FileNotFoundError, FileExistsError, ValueError) as exc:
                results.append({"file_id": file_id, "status": "failed", "error": str(exc)})
            except RedisError:
                results.append({"file_id": file_id, "status": "failed", "error": "切块队列暂不可用"})
            else:
                results.append({
                    "file_id": file_id, "task_id": task_id, "status": "queued",
                    "embedding_model_id": model.id, **params,
                })
        return results

    @staticmethod
    def _check(item: FileInfo | None) -> FileInfo:
        if item is None:
            raise FileNotFoundError("文件不存在")
        if item.parse_status != "completed" or not item.parsed_object_name:
            raise ValueError("请先完成文件解析")
        if item.split_status == "processing":
            raise FileExistsError("文件正在切块")
        if item.ingest_status == "processing":
            raise FileExistsError("文件正在向量入库")
        return item

    def split_file(self, file_id: int, parent_size: int, child_size: int, overlap: int) -> dict[str, Any]:
        """任务领取后释放行锁；慢速读写在事务外执行，结果一次性替换提交。"""
        with self.db.session() as session:
            item = self._check(file_dao.get_for_update(session, file_id))
            splitter = FileSplitter(item.extension, parent_size, child_size, overlap)
            BaseDao.update(session, item, {"split_status": "processing", "error": ""})

        try:
            with self.minio.download(item.bucket, item.parsed_object_name) as response:
                payload = json.load(response)
            documents = [Document(**document) for document in payload["documents"]]
            groups: list[tuple[ChunkInfo, list[ChunkInfo]]] = []
            index = 0
            for parent, children in splitter.split(documents):
                parent_item = self._chunk(file_id, parent, index)
                index += 1
                child_items = []
                for child in children:
                    child_items.append(self._chunk(file_id, child, index))
                    index += 1
                groups.append((parent_item, child_items))

            with self.db.session() as session:
                current = file_dao.get_for_update(session, file_id)
                if current is None:
                    raise FileNotFoundError("文件不存在")
                # 旧块替换与完成状态共用一个事务，任何写入失败均保留原有块。
                chunk_dao.replace(session, file_id, groups)
                BaseDao.update(session, current, {
                    "split_status": "completed", "ingest_status": "pending", "error": "",
                })
            return {
                "file_id": file_id, "status": "completed", "parent_count": len(groups),
                "child_count": sum(len(children) for _, children in groups),
                "parent_size": parent_size, "child_size": child_size, "overlap": overlap,
            }
        except Exception as exc:
            try:
                with self.db.session() as session:
                    current = BaseDao.get(session, FileInfo, file_id)
                    if current is not None:
                        BaseDao.update(session, current, {"split_status": "failed", "error": str(exc)})
            except Exception:
                logger.exception("记录文件切块失败状态时发生错误，file_id=%s", file_id)
            raise

    @staticmethod
    def _chunk(file_id: int, document: Document, index: int) -> ChunkInfo:
        """元数据保留标题路径及结构边界，后续检索可按父块还原上下文。"""
        return ChunkInfo(
            file_id=file_id, content=document.page_content, chunk_index=index,
            content_hash=hashlib.sha256(document.page_content.encode("utf-8")).hexdigest(),
            page_start=document.metadata.get("page_number"),
            page_end=document.metadata.get("page_number"), meta=dict(document.metadata),
        )


def run_split_task(
    file_id: int, parent_size: int, child_size: int, overlap: int,
    embedding_model_id: int | None = None,
) -> dict[str, Any]:
    """在同一队列任务中先完成切块，再批量向量化；入库失败保留已经切好的块。"""
    service = SplitService()
    result = service.split_file(file_id, parent_size, child_size, overlap)
    result.update(IngestService(service.db).ingest_file(file_id, embedding_model_id))
    return result
