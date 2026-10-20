"""缓存 YAML 配置，支持容器服务地址覆盖及布尔值转换。"""

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import yaml

_MISSING = object()


class Config:
    """读取 YAML 字典，多级配置使用 config["mysql"]["host"]。"""

    @staticmethod
    @lru_cache(maxsize=1)
    def _read() -> dict[str, Any]:
        """首次读取项目根目录的配置文件，后续调用复用缓存。"""
        path = Path(__file__).resolve().parents[2] / "config.yaml"
        with path.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError("config.yaml 必须是 YAML 映射")
        # 容器通过服务名连接数据库，本机仍沿用 YAML；凭据继续从挂载配置读取。
        for name, section, field in (
            ("MYSQL_HOST", "mysql", "host"),
            ("REDIS_HOST", "redis", "host"),
            ("MILVUS_URI", "milvus", "uri"),
            ("MINIO_ENDPOINT", "minio", "endpoint"),
        ):
            if name in os.environ:
                data[section][field] = os.environ[name]
        return data

    @staticmethod
    def get(key: str | None = None, default: Any = _MISSING) -> Any:
        """不传 key 时返回全部配置；未指定默认值时，缺失的键会抛出异常。"""
        data = Config._read()
        if key is None:
            return data
        if default is _MISSING:
            return data[key]
        return data.get(key, default)

    @staticmethod
    def to_bool(value: Any) -> bool:
        """接受布尔值或忽略大小写、首尾空白的 true/false 字符串。"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "false"):
                return normalized == "true"
        raise ValueError("配置值必须是 true 或 false")
