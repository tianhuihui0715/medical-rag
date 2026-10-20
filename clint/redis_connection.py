"""按项目配置创建 Redis 客户端及阻塞连接池。"""

from threading import Lock

from redis import BlockingConnectionPool, Connection, Redis, SSLConnection

from common.config.config import Config


class RedisConnection:
    """封装 Redis 客户端及带等待超时的连接池。"""
    def __init__(self, decode_responses: bool = True):
        config = Config.get()
        self.pool = BlockingConnectionPool(
            connection_class=(
                SSLConnection if Config.to_bool(config["redis"]["ssl"]) else Connection
            ),
            host=config["redis"]["host"],
            port=int(config["redis"]["port"]),
            db=int(config["redis"]["database"]),
            password=config["redis"]["password"] or None,
            max_connections=int(config["redis"]["max_connections"]),
            timeout=int(config["redis"]["pool_timeout"]),
            socket_connect_timeout=float(config["redis"]["connect_timeout"]),
            socket_timeout=float(config["redis"]["socket_timeout"]),
            decode_responses=decode_responses,
        )
        self.client = Redis(connection_pool=self.pool)

    def close(self) -> None:
        self.client.close()
        self.pool.disconnect()


_redis: RedisConnection | None = None
_lock = Lock()


def get_redis_connection() -> RedisConnection:
    """共享任务队列连接池，保留字节响应以兼容 RQ 的任务序列化。"""
    global _redis
    with _lock:
        if _redis is None:
            _redis = RedisConnection(decode_responses=False)
        return _redis
