"""加载项目内 BGE-M3，以单个推理线程返回稠密向量及稀疏词权重。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

from service.config_service import ConfigService


class EmbeddingService:
    """仅在应用启动时创建，队列通过 HTTP 调用，不在任务进程中加载模型。"""
    name = "bge-m3"

    def __init__(self, config: ConfigService | None = None):
        # 延迟导入，队列导入业务模块时不会加载推理依赖或模型。
        from milvus_model.hybrid import BGEM3EmbeddingFunction

        config = config if config is not None else ConfigService()
        path = Path(cast(str, config.get_value("local_embedding_path")))
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        device = cast(str, config.get_value("local_embedding_device"))
        self.model: Any = BGEM3EmbeddingFunction(
            model_name=str(path), device=device, devices=device,
            use_fp16=device != "cpu",
            batch_size=int(cast(str, config.get_value("embedding_batch_size"))),
            return_dense=True, return_sparse=True, return_colbert_vecs=False,
            passage_max_length=8192, local_files_only=True,
        )
        # 独立线程串行推理，不阻塞事件循环或占满普通接口使用的线程池。
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedding")

    async def embed(self, texts: list[str], model: str) -> dict[str, Any]:
        """所有请求复用同一模型；多请求排队执行，控制推理峰值内存。"""
        if model != self.name:
            raise LookupError("本地向量模型不存在")
        return await asyncio.get_running_loop().run_in_executor(self.executor, self._encode, texts)

    def _encode(self, texts: list[str]) -> dict[str, Any]:
        """一次推理生成双向量；稀疏矩阵按行转为 JSON 可传输的 token 权重字典。"""
        rows = []
        if texts:
            result = self.model.encode_documents(texts)
            sparse = result["sparse"].tocsr()
            for index, vector in enumerate(result["dense"]):
                start, end = sparse.indptr[index:index + 2]
                rows.append({
                    "object": "embedding", "index": index, "embedding": vector.tolist(),
                    "sparse_embedding": {
                        str(int(token)): float(weight)
                        for token, weight in zip(sparse.indices[start:end], sparse.data[start:end])
                    },
                })
        return {"object": "list", "model": self.name, "data": rows}

    def close(self) -> None:
        """退出时等待已开始的推理结束，取消未开始的请求并释放模型引用。"""
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.model = None
