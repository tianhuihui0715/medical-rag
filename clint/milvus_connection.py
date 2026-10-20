"""管理共享 Milvus 客户端，统一设置连接与请求超时，关闭请求隐式重试。"""

from threading import Lock
from typing import Any, Literal

from pymilvus import MilvusClient

from common.config.config import Config


class MilvusConnection:
    """封装指定数据库的 Milvus 客户端。"""
    def __init__(self):
        config = Config.get()
        self.timeout = float(config["milvus"]["timeout"])
        self.client = MilvusClient(
            uri=config["milvus"]["uri"],
            db_name=config["milvus"]["database"],
            token=config["milvus"]["token"],
            timeout=self.timeout,
        )
        self.closed = False

    def call(
        self,
        method: Literal[
            "has_collection", "create_collection", "describe_collection", "upsert",
            "delete", "search", "hybrid_search", "query",
        ],
        *args: Any, **kwargs: Any,
    ) -> Any:
        """统一集合及向量读写超时；失败直接抛出，由业务层决定是否重试。"""
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        # SDK 对浮点 timeout 的重试期限处理不一致，禁用隐式重试以免长时间阻塞。
        kwargs["retry_times"] = 0
        return getattr(self.client, method)(*args, **kwargs)

    def close(self) -> None:
        self.client.close()
        self.closed = True


_connection: MilvusConnection | None = None
_lock = Lock()


def get_milvus_connection() -> MilvusConnection:
    """同一进程复用客户端，关闭后允许重新建立连接。"""
    global _connection
    with _lock:
        if _connection is None or _connection.closed:
            _connection = MilvusConnection()
        return _connection
