"""缓存业务配置值，供同一进程中的不同请求共享。"""

from collections.abc import Callable
from threading import RLock
from time import monotonic
from weakref import WeakKeyDictionary

from clint.mysql_connection import MySQLConnection


class ConfigCache:
    """按数据库对象隔离缓存，修改后主动清除，其他进程的修改最多延迟 60 秒。"""
    _lock = RLock()
    _ttl = 60
    _values: WeakKeyDictionary[
        MySQLConnection, dict[str, tuple[float, str | tuple[str, ...]]]
    ] = WeakKeyDictionary()

    @classmethod
    def get(
        cls, db: MySQLConnection, key: str, loader: Callable[[], str | list[str]],
    ) -> str | list[str]:
        """未命中或过期时加载；锁同时避免并发回源和清除后写回旧值。"""
        with cls._lock:
            values = cls._values.setdefault(db, {})
            entry = values.get(key)
            if entry is None or entry[0] <= monotonic():
                value = loader()
                # 列表以不可变形式缓存，每次返回副本，避免调用方修改共享配置。
                entry = (monotonic() + cls._ttl, tuple(value) if isinstance(value, list) else value)
                values[key] = entry
            result = entry[1]
            return list(result) if isinstance(result, tuple) else result

    @classmethod
    def clear(cls, db: MySQLConnection) -> None:
        """清除指定数据库的配置缓存，应在写事务成功提交后调用。"""
        with cls._lock:
            cls._values.pop(db, None)
