"""复用 HTTP 连接池调用模型 API，请求独立携带地址、密钥及超时。"""

from threading import Lock
from typing import Any

import httpx

from model.model_provider_info import ModelProviderInfo


class ModelConnection:
    def __init__(self):
        self.client = httpx.Client()

    def call(
        self, provider: ModelProviderInfo, path: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        """路径追加在 API 根地址后；返回服务原始 JSON，供业务调用方使用。"""
        url = f"{provider.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
        response = self.client.post(url, json=payload, headers=headers, timeout=provider.timeout)
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("模型服务返回了无效的 JSON") from None
        if not isinstance(result, dict):
            raise RuntimeError("模型服务返回的数据格式不正确")
        return result

    def close(self) -> None:
        self.client.close()


_connection: ModelConnection | None = None
_lock = Lock()


def get_model_connection() -> ModelConnection:
    """首次使用时创建客户端，同一进程中的请求共享连接池。"""
    global _connection
    with _lock:
        if _connection is None or _connection.client.is_closed:
            _connection = ModelConnection()
        return _connection
