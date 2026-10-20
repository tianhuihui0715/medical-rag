"""封装 Milvus 双向量集合的建库、写入、权限过滤检索和清理。"""

from typing import Any

from pymilvus import AnnSearchRequest, DataType, MilvusClient, MilvusException, WeightedRanker

from clint.milvus_connection import MilvusConnection, get_milvus_connection


class VectorDao:
    """MySQL 子块 ID 作为向量主键，父块正文仍保存在 MySQL。"""
    def __init__(self, connection: MilvusConnection | None = None):
        self.connection = connection if connection is not None else get_milvus_connection()
        self.client = self.connection.client

    def ensure_collection(self, name: str, dimension: int, sparse: bool = False) -> None:
        """按模型输出建集合；已有集合核对维度及稀疏字段，不覆盖结构和数据。"""
        if not self.connection.call("has_collection", name):
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("file_id", DataType.INT64)
            schema.add_field("parent_id", DataType.INT64)
            schema.add_field("model_id", DataType.INT64)
            schema.add_field("role_ids", DataType.JSON)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
            if sparse:
                schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
            indexes = self.client.prepare_index_params()
            indexes.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            indexes.add_index(field_name="file_id", index_type="INVERTED")
            if sparse:
                indexes.add_index(
                    field_name="sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="IP",
                )
            try:
                self.connection.call("create_collection", name, schema=schema, index_params=indexes)
            except MilvusException:
                # 多个文件可能同时首次建集合，仅兼容集合已由其他任务创建的情况。
                if not self.connection.call("has_collection", name):
                    raise
        info = self.connection.call("describe_collection", name)
        vector = next(field for field in info["fields"] if field["name"] == "vector")
        if int(vector["params"]["dim"]) != dimension:
            raise ValueError("Milvus 集合维度与模型输出不一致，请使用匹配的集合")
        sparse_field = next((field for field in info["fields"] if field["name"] == "sparse_vector"), None)
        if (sparse_field is not None) != sparse or (
            sparse_field is not None and sparse_field["type"] != DataType.SPARSE_FLOAT_VECTOR
        ):
            raise ValueError("Milvus 集合的稀疏字段与模型输出不一致，请使用匹配的集合")

    def write_vectors(self, name: str, rows: list[dict[str, Any]]) -> None:
        """以子块 ID 幂等写入，网络超时后的重新执行不会生成重复主键。"""
        if rows:
            result = self.connection.call("upsert", name, rows)
            if result["upsert_count"] != len(rows):
                raise RuntimeError("Milvus 向量写入数量不完整")

    def delete_file(self, name: str, file_id: int) -> None:
        """仅清理指定文件的派生向量，不删除集合或其他文件的数据。"""
        if self.connection.call("has_collection", name):
            self.connection.call("delete", name, filter=f"file_id == {file_id}")

    def search(
        self, name: str, file_ids: list[int], dense: list[float], sparse: dict[int, float],
        recall_k: int, sparse_weight: float,
    ) -> list[dict[str, Any]]:
        """两路先使用相同文件范围过滤，再按动态权重融合，统一沿用连接层超时。"""
        if not file_ids:
            return []
        scope = f"file_id in {file_ids}"
        requests = [AnnSearchRequest(
            data=[dense], anns_field="vector", param={"metric_type": "COSINE"},
            limit=recall_k, expr=scope,
        )]
        weights = [1 - sparse_weight]
        if sparse:
            requests.append(AnnSearchRequest(
                data=[sparse], anns_field="sparse_vector", param={"metric_type": "IP"},
                limit=recall_k, expr=scope,
            ))
            weights.append(sparse_weight)
        else:
            # 没有有效词权重时只执行稠密检索，避免空稀疏向量使整个请求失败。
            weights = [1.0]
        result = self.connection.call(
            "hybrid_search", name, reqs=requests, ranker=WeightedRanker(*weights), limit=recall_k,
            output_fields=["file_id", "parent_id"], consistency_level="Strong",
        )
        return result[0]
