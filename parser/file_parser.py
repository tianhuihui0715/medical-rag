"""协调文件解析、解析结果持久化、原文件归档和状态维护。"""

from collections.abc import Callable
from io import BytesIO
import json
import logging
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryDirectory
from typing import Any, cast

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from clint.minio_connection import MinIOConnection, get_minio_connection
from clint.mysql_connection import MySQLConnection, get_mysql_connection
from dao import file_dao
from dao.base_dao import BaseDao
from model.file_info import FileInfo
from service.config_service import ConfigService

logger = logging.getLogger(__name__)


class FileParser:
    """共用存储和事务处理，具体文件格式交给 LangChain Loader。"""
    def __init__(
        self, db: MySQLConnection | None = None, minio: MinIOConnection | None = None,
    ):
        self.db = db if db is not None else get_mysql_connection()
        self.minio = minio if minio is not None else get_minio_connection()

    def parse(self, file_id: int, loader: Callable[[str], BaseLoader]) -> list[Document]:
        """领取任务后释放事务，解析并保存 JSON，存储成功后更新文件位置及状态。"""
        with self.db.session() as session:
            item = file_dao.get_for_update(session, file_id)
            if item is None:
                raise FileNotFoundError("文件不存在")
            if item.parse_status == "processing":
                raise FileExistsError("文件正在解析")
            if item.split_status == "processing":
                raise FileExistsError("文件正在切块")
            if item.ingest_status == "processing":
                raise FileExistsError("文件正在向量入库")
            BaseDao.update(session, item, {"parse_status": "processing", "error": ""})

        try:
            # Loader 使用本地路径；源文件流式落入临时目录，完成或失败后均自动清理。
            with TemporaryDirectory(prefix="rag-parse-") as directory:
                path = Path(directory) / f"source.{item.extension}"
                with self.minio.download(item.bucket, item.object_name) as source:
                    with path.open("wb") as target:
                        copyfileobj(source, target, length=1024 * 1024)
                documents = loader(str(path)).load()

            target_bucket = cast(str, ConfigService(self.db).get_value("upload_final_bucket"))
            for document in documents:
                # 替换 Loader 产生的临时路径及时间，保留标题、表格等结构元数据。
                document.metadata.pop("file_directory", None)
                document.metadata.pop("last_modified", None)
                document.metadata.update({
                    "file_id": file_id,
                    "source": item.source_path or item.name,
                    "filename": Path(item.name.replace("\\", "/")).name,
                    "bucket": target_bucket,
                    "object_name": item.object_name,
                })

            parsed_object_name = f"parsed/{file_id}.json"
            data = json.dumps({
                "file_id": file_id,
                "documents": [
                    {"page_content": document.page_content, "metadata": document.metadata}
                    for document in documents
                ],
            }, ensure_ascii=False).encode("utf-8")
            with BytesIO(data) as stream:
                self.minio.upload(target_bucket, parsed_object_name, stream, len(data), "application/json")
            if item.bucket != target_bucket:
                self.minio.copy(item.bucket, item.object_name, target_bucket)
            # 结果和原文件均保存成功后提交位置及完成状态，再删除临时源文件以保留失败重试能力。
            self._update(file_id, {
                "bucket": target_bucket,
                "parsed_object_name": parsed_object_name,
                "parse_status": "completed",
                "split_status": "pending",
                "ingest_status": "pending",
                "error": "",
            })
            if item.bucket != target_bucket:
                try:
                    self.minio.delete(item.bucket, item.object_name)
                except Exception:
                    logger.exception("正式文件已保存，清理临时对象失败：%s/%s", item.bucket, item.object_name)
            return documents
        except Exception as exc:
            try:
                self._update(file_id, {"parse_status": "failed", "error": str(exc)})
            except Exception:
                logger.exception("记录文件解析失败状态时发生错误，file_id=%s", file_id)
            raise

    def _update(self, file_id: int, values: dict[str, Any]) -> None:
        with self.db.session() as session:
            item = BaseDao.get(session, FileInfo, file_id)
            if item is None:
                raise FileNotFoundError("文件不存在")
            BaseDao.update(session, item, values)
