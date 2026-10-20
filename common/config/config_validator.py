"""启动时检查登录、文件处理、向量检索和本地模型所需的数据库配置。"""

from common.config.config_cache import ConfigCache
from service.config_service import ConfigService


class ConfigValidator:
    """统一检查业务配置格式及模型推理所必需的有效参数。"""
    def __init__(self, config: ConfigService | None = None):
        self.config = config if config is not None else ConfigService()

    def validate(self) -> None:
        """配置缺失或格式不符合要求时抛出 ValueError。"""
        # 启动时重新核对数据库配置，并为后续请求预热缓存。
        ConfigCache.clear(self.config.db)
        types = self.config.get_value("upload_file_types")
        if not isinstance(types, list) or not types:
            raise ValueError("upload_file_types 需要配置非空字典列表")

        values: dict[str, str] = {}
        for key in (
            "upload_max_size_mb",
            "upload_temp_bucket",
            "upload_final_bucket",
            "vector_collection_prefix",
            "local_embedding_path",
            "local_embedding_device",
            "local_rerank_path",
            "local_rerank_device",
        ):
            value = self.config.get_value(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} 需要配置非空单值")
            values[key] = value

        try:
            float(values["upload_max_size_mb"])
        except ValueError:
            raise ValueError("upload_max_size_mb 需要配置数字") from None

        for key in (
            "chunk_parent_size", "chunk_child_size", "chunk_overlap",
            "embedding_batch_size", "login_expire_seconds",
            "rerank_batch_size", "search_recall_k", "search_top_k",
        ):
            value = self.config.get_value(key)
            if not isinstance(value, str):
                raise ValueError(f"{key} 需要配置整数单值")
            try:
                number = int(value)
            except ValueError:
                raise ValueError(f"{key} 需要配置整数单值") from None
            if key in (
                "embedding_batch_size", "login_expire_seconds", "rerank_batch_size",
                "search_recall_k", "search_top_k",
            ) and number <= 0:
                raise ValueError(f"{key} 必须大于 0")

        for key in ("search_sparse_weight", "search_exact_sparse_weight"):
            value = self.config.get_value(key)
            if not isinstance(value, str):
                raise ValueError(f"{key} 需要配置数字单值")
            weight = float(value)
            if not 0 <= weight <= 1:
                raise ValueError(f"{key} 必须在 0 到 1 之间")

