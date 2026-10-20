"""封装 Redis 文件解析、切块与向量入库队列，提供独立消费者启动入口。"""

from collections.abc import Callable
from typing import Any

from rq import Queue, SpawnWorker

from clint.redis_connection import RedisConnection, get_redis_connection


class ParseQueue:
    """将文件处理函数、文件 ID 及参数加入队列，由独立 Worker 执行。"""
    def __init__(self, redis: RedisConnection | None = None):
        self.redis = redis if redis is not None else get_redis_connection()
        # 批量向量化可能超过 RQ 默认 180 秒，文件任务最长执行 30 分钟。
        self.queue = Queue("file_parse", connection=self.redis.client, default_timeout=1800)

    def enqueue(self, task: Callable[..., object], file_id: int, **kwargs: Any) -> str:
        """返回任务 ID，保存本次已经确定的参数，配置后续变更不影响该任务。"""
        job = self.queue.enqueue(task, args=(file_id,), kwargs=kwargs)
        return job.id

    def work(self) -> None:
        """独立进程消费任务，使用 spawn 避免 macOS 下 fork 加载解析依赖失败。"""
        SpawnWorker([self.queue], connection=self.redis.client).work()


if __name__ == "__main__":
    connection = RedisConnection(decode_responses=False)
    try:
        ParseQueue(connection).work()
    finally:
        connection.close()
