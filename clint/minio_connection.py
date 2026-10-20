"""管理 MinIO 客户端和 HTTP 连接池，封装桶及对象存储操作。"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import BinaryIO

from minio import Minio
from minio.commonconfig import CopySource, SnowballObject
from minio.error import S3Error
from urllib3 import PoolManager, Timeout
from urllib3.response import BaseHTTPResponse

from common.config.config import Config


class _HTTPPool(PoolManager):
    """为阻塞连接池补充获取连接时的等待超时。"""
    def urlopen(self, method, url, redirect=True, **kwargs):
        config = Config.get()
        # block=True 时也限制等待池中空闲连接的时间。
        kwargs.setdefault(
            "pool_timeout", float(config["minio"]["pool_timeout"])
        )
        return super().urlopen(method, url, redirect=redirect, **kwargs)


class MinIOConnection:
    """封装 MinIO 桶和对象操作，共用 HTTP 连接池。"""
    def __init__(self):
        config = Config.get()
        self.http = _HTTPPool(
            maxsize=int(config["minio"]["pool_size"]),
            block=True,
            timeout=Timeout(
                connect=float(config["minio"]["connect_timeout"]),
                read=float(config["minio"]["read_timeout"]),
            ),
            cert_reqs="CERT_REQUIRED",
            retries=False,
        )
        self.client = Minio(
            endpoint=config["minio"]["endpoint"],
            access_key=config["minio"]["access_key"],
            secret_key=config["minio"]["secret_key"],
            secure=Config.to_bool(config["minio"]["secure"]),
            http_client=self.http,
        )

    def ensure_bucket(self, bucket: str) -> None:
        """桶不存在时创建，兼容并发创建导致的已归属当前用户异常。"""
        if self.client.bucket_exists(bucket):
            return
        try:
            self.client.make_bucket(bucket)
        except S3Error as exc:
            if exc.code != "BucketAlreadyOwnedByYou":
                raise

    def upload(
        self,
        bucket: str,
        object_name: str,
        data: BinaryIO,
        size: int,
        content_type: str = "application/octet-stream",
    ) -> None:
        """确保目标桶存在后上传数据流，size 的单位为字节。"""
        self.ensure_bucket(bucket)
        self.client.put_object(bucket, object_name, data, size, content_type=content_type)

    def upload_many(
        self, bucket: str, files: Iterable[tuple[str, BinaryIO, int]],
    ) -> None:
        """将对象名、数据流、字节数打包批量上传，由 MinIO 解包成独立对象。"""
        self.ensure_bucket(bucket)
        objects = (
            SnowballObject(name, data=data, length=size)
            for name, data, size in files
        )
        # TAR 暂存磁盘，避免整批文件占用内存；请求结束后自动清理本地临时文件。
        with TemporaryDirectory(prefix="rag-upload-") as directory:
            self.client.upload_snowball_objects(
                bucket, objects, staging_filename=str(Path(directory) / "upload.tar"),
            )

    @contextmanager
    def download(self, bucket: str, object_name: str) -> Iterator[BaseHTTPResponse]:
        """流式读取对象，使用结束后释放 HTTP 连接。"""
        response = self.client.get_object(bucket, object_name)
        try:
            yield response
        finally:
            response.close()
            response.release_conn()

    def delete(self, bucket: str, object_name: str) -> None:
        self.client.remove_object(bucket, object_name)

    def copy(self, bucket: str, object_name: str, target_bucket: str) -> None:
        """保留对象名复制到目标桶，源对象由调用方决定何时删除。"""
        if bucket == target_bucket:
            return
        self.ensure_bucket(target_bucket)
        self.client.copy_object(target_bucket, object_name, CopySource(bucket, object_name))

    def move(self, bucket: str, object_name: str, target_bucket: str) -> None:
        """保留对象名跨桶迁移；复制失败时保留源对象。"""
        if bucket == target_bucket:
            return
        self.copy(bucket, object_name, target_bucket)
        self.delete(bucket, object_name)

    def close(self) -> None:
        self.http.clear()


_minio: MinIOConnection | None = None
_lock = Lock()


def get_minio_connection() -> MinIOConnection:
    """获取进程内共享的 MinIO 客户端和 HTTP 连接池。"""
    global _minio
    with _lock:
        if _minio is None:
            _minio = MinIOConnection()
        return _minio
