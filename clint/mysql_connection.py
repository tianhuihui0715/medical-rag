"""管理共享 MySQL 连接池，并为业务操作提供独立事务会话。"""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import URL
from sqlmodel import Session, create_engine

from common.config.config import Config


class MySQLConnection:
    """维护连接池，通过 session 上下文控制单次业务事务。"""
    def __init__(self):
        config = Config.get()
        url = URL.create(
            "mysql+pymysql",
            username=config["mysql"]["username"],
            password=config["mysql"]["password"],
            host=config["mysql"]["host"],
            port=int(config["mysql"]["port"]),
            database=config["mysql"]["database"],
            query={"charset": "utf8mb4"},
        )
        self.engine = create_engine(
            url,
            pool_size=int(config["mysql"]["pool_size"]),
            max_overflow=int(config["mysql"]["max_overflow"]),
            pool_timeout=float(config["mysql"]["pool_timeout"]),
            pool_recycle=int(config["mysql"]["pool_recycle"]),
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "connect_timeout": int(config["mysql"]["connect_timeout"]),
                "read_timeout": float(config["mysql"]["read_timeout"]),
                "write_timeout": float(config["mysql"]["write_timeout"]),
            },
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """每次操作独立 Session，正常提交、异常回滚，结束后归还连接。"""
        with Session(self.engine, expire_on_commit=False) as session:
            with session.begin():
                yield session

    def close(self) -> None:
        self.engine.dispose()


_db: MySQLConnection | None = None
_lock = Lock()


def get_mysql_connection() -> MySQLConnection:
    """获取进程内共享的数据库对象，首次使用时创建连接池。"""
    global _db
    with _lock:
        if _db is None:
            _db = MySQLConnection()
        return _db
