"""文件业务：上传并关联知识库，保存文件元数据及提交解析任务。"""

import hashlib
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import UploadFile
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError, OperationalError

from clint.minio_connection import MinIOConnection, get_minio_connection
from clint.mysql_connection import MySQLConnection, get_mysql_connection
from task.parse_queue import ParseQueue
from dao import file_dao, knowledge_dao
from dao.base_dao import BaseDao
from model.file_info import FileInfo, FileUpload
from model.knowledge_base_info import KnowledgeBaseInfo
from parser import md_parser, text_parser
from service.config_service import ConfigService


class FileService:
    """协调上传校验、对象存储及文件元数据保存。"""
    def __init__(
        self,
        config: ConfigService | None = None,
        minio: MinIOConnection | None = None,
        queue: ParseQueue | None = None,
        *,
        db: MySQLConnection | None = None,
    ):
        # 显式数据库优先；兼容只传配置对象的调用，否则使用共享连接池。
        self.db = db if db is not None else (
            config.db if config is not None else get_mysql_connection()
        )
        self.config = config if config is not None else ConfigService(self.db)
        self.minio = minio if minio is not None else get_minio_connection()
        self.queue = queue
        # 从跨请求缓存读取当前配置快照，配置更新后新实例获取刷新后的值。
        self.file_types = cast(list[str], self.config.get_value("upload_file_types"))
        self.max_size_mb = float(cast(str, self.config.get_value("upload_max_size_mb")))
        self.temp_bucket = cast(str, self.config.get_value("upload_temp_bucket"))

    def list_accessible_files(self, user_id: int, file_ids: list[int] | None = None) -> list[FileInfo]:
        """读取用户当前可检索的文件，供列表接口及后续 Milvus 权限过滤复用。"""
        with self.db.session() as session:
            return file_dao.list_accessible(session, user_id, file_ids)

    def start_parse(self, file_ids: list[int]) -> list[dict[str, Any]]:
        """批量查询后逐文件入队；重复 ID 仅提交一次，单项失败不影响其他文件。"""
        file_ids = list(dict.fromkeys(file_ids))
        if not file_ids:
            return []
        with self.db.session() as session:
            items = file_dao.get_by_ids(session, file_ids)
        parsers = {"txt": text_parser.parse, "md": md_parser.parse}
        queue = self.queue
        results: list[dict[str, Any]] = []
        for file_id in file_ids:
            try:
                item = items.get(file_id)
                if item is None:
                    raise FileNotFoundError("文件不存在")
                if "processing" in (item.parse_status, item.split_status, item.ingest_status):
                    raise FileExistsError("文件正在解析、切块或向量入库")
                parser = parsers.get(item.extension.lower())
                if parser is None:
                    raise ValueError("当前仅支持 txt、md 文件解析")
                queue = queue if queue is not None else ParseQueue()
                task_id = queue.enqueue(parser, file_id)
            except (FileNotFoundError, FileExistsError, ValueError) as exc:
                results.append({"file_id": file_id, "status": "failed", "error": str(exc)})
            except RedisError:
                results.append({"file_id": file_id, "status": "failed", "error": "解析队列暂不可用"})
            else:
                # 入队仅表示已接受任务，实际解析状态由 Worker 更新。
                results.append({"file_id": file_id, "task_id": task_id, "status": "queued"})
        return results

    def upload(
        self, file: UploadFile, source_path: str = "", knowledge_id: int | None = None,
    ) -> FileUpload:
        """同内容文件复用记录并补充知识库关联；新文件先上传，再原子保存元数据及关联。"""
        item = self._prepare(file, source_path)
        self._check_knowledge(knowledge_id)
        key = self._key(item)
        existing = self._existing([item]).get(key)
        if existing is not None:
            _, _, target_id = self._save_many([], knowledge_id, {key: existing})
            return self._result(existing, item.name, True, target_id)
        position = file.file.tell()
        try:
            file.file.seek(0)
            self.minio.upload(self.temp_bucket, item.object_name, file.file, item.size, item.content_type)
        finally:
            file.file.seek(position)

        saved, created, target_id = self._save_many([item], knowledge_id)
        return self._result(saved[key], item.name, key not in created, target_id)

    def upload_many(
        self, files: list[UploadFile], source_paths: list[str] | None = None,
        knowledge_id: int | None = None,
    ) -> list[FileUpload]:
        """一批文件关联同一知识库，跳过重复内容和关联，结果与输入顺序一致。"""
        if source_paths is not None and len(source_paths) != len(files):
            raise ValueError("来源路径数量必须与文件数量一致")
        if not files:
            return []
        items = [
            self._prepare(file, source_paths[index] if source_paths is not None else "")
            for index, file in enumerate(files)
        ]
        self._check_knowledge(knowledge_id)
        existing = self._existing(items)
        pending: dict[tuple[str, int], tuple[UploadFile, FileInfo]] = {}
        for file, item in zip(files, items):
            key = self._key(item)
            if key not in existing and key not in pending:
                pending[key] = (file, item)
        if pending:
            uploads = list(pending.values())
            positions = [file.file.tell() for file, _ in uploads]
            try:
                for file, _ in uploads:
                    file.file.seek(0)
                self.minio.upload_many(
                    self.temp_bucket,
                    [(item.object_name, file.file, item.size) for file, item in uploads],
                )
            finally:
                for (file, _), position in zip(uploads, positions):
                    file.file.seek(position)
        existing, created, target_id = self._save_many(
            [item for _, item in pending.values()], knowledge_id, existing,
        )

        results: list[FileUpload] = []
        seen: set[tuple[str, int]] = set()
        for item in items:
            key = self._key(item)
            duplicate = key not in created or key in seen
            results.append(self._result(existing[key], item.name, duplicate, target_id))
            seen.add(key)
        return results

    def _existing(self, items: list[FileInfo]) -> dict[tuple[str, int], FileInfo]:
        with self.db.session() as session:
            return file_dao.get_by_hashes(session, [cast(str, item.content_hash) for item in items])

    def _check_knowledge(self, knowledge_id: int | None) -> None:
        """上传对象前检查指定知识库；默认知识库延迟到文件成功保存时创建。"""
        if knowledge_id is not None:
            with self.db.session() as session:
                item = BaseDao.get(session, KnowledgeBaseInfo, knowledge_id)
                if item is None or item.is_deleted:
                    raise FileNotFoundError("知识库不存在")

    def _save_many(
        self, items: list[FileInfo], knowledge_id: int | None,
        existing: dict[tuple[str, int], FileInfo] | None = None,
    ) -> tuple[dict[tuple[str, int], FileInfo], set[tuple[str, int]], int]:
        """文件与关联同事务保存；并发重复文件复用，默认库初始化死锁仅有限重试。"""
        saved = dict(existing or {})
        created: set[tuple[str, int]] = set()
        pending = items
        deadlocks = 0
        while True:
            try:
                with self.db.session() as session:
                    target = knowledge_dao.get_for_upload(session, knowledge_id)
                    rows = file_dao.add_many(session, pending)
                    current = {**saved, **{self._key(item): item for item in rows}}
                    target_id = cast(int, target.id)
                    knowledge_dao.add_files(session, target_id, [cast(int, item.id) for item in current.values()])
            except OperationalError as exc:
                # 空表首次并发创建默认库可能触发 MySQL 间隙锁死锁，回滚后重试整个事务。
                if not exc.orig.args or exc.orig.args[0] != 1213 or deadlocks >= 2:
                    raise
                deadlocks += 1
            except IntegrityError:
                # 先退出失败事务再查询；每次冲突必须移除已存在项，避免无效重试。
                existing = self._existing(pending)
                if not existing:
                    raise
                saved.update(existing)
                pending = [item for item in pending if self._key(item) not in existing]
            else:
                saved.update((self._key(item), item) for item in rows)
                created.update(self._key(item) for item in rows)
                break
        return saved, created, target_id

    @staticmethod
    def _key(item: FileInfo) -> tuple[str, int]:
        return cast(str, item.content_hash), item.size

    @staticmethod
    def _result(item: FileInfo, upload_name: str, duplicate: bool, knowledge_id: int) -> FileUpload:
        return FileUpload.model_validate(item, update={
            "knowledge_id": knowledge_id,
            "upload_name": upload_name,
            "duplicate": duplicate,
            "message": "文件已存在，已复用已有记录" if duplicate else "上传成功",
        })

    def _prepare(self, file: UploadFile, source_path: str) -> FileInfo:
        """校验文件并分段计算 SHA-256，恢复数据流位置后返回元数据。"""
        name = Path((file.filename or "").replace("\\", "/")).name
        extension = Path(name).suffix.lower().lstrip(".")
        if extension not in self.file_types:
            raise ValueError("不支持的文件类型")

        position = file.file.tell()
        try:
            file.file.seek(0, 2)
            size = file.file.tell()
            if size > self.max_size_mb * 1024 * 1024:
                raise ValueError(f"文件大小不能超过 {self.max_size_mb:g} MB")
            file.file.seek(0)
            digest = hashlib.sha256()
            while data := file.file.read(1024 * 1024):
                digest.update(data)
        finally:
            file.file.seek(position)

        return FileInfo(
            name=file.filename or "",
            size=size,
            extension=extension,
            content_type=file.content_type or "application/octet-stream",
            content_hash=digest.hexdigest(),
            source_path=source_path or file.filename or "",
            bucket=self.temp_bucket,
            object_name=f"{uuid4().hex}_{name}",
        )
