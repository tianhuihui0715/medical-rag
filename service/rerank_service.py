"""加载本地 BGE 重排模型，以单线程为完整文档分窗口评分。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

from service.config_service import ConfigService


class RerankService:
    """主进程持有一份模型，HTTP 请求排队复用；长文档取各窗口最高相关性。"""
    name = "bge-reranker-large"

    def __init__(self, config: ConfigService | None = None):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        config = config if config is not None else ConfigService()
        path = Path(cast(str, config.get_value("local_rerank_path")))
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        self.device = cast(str, config.get_value("local_rerank_device"))
        self.batch_size = int(cast(str, config.get_value("rerank_batch_size")))
        self.tokenizer: Any = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self.model: Any = AutoModelForSequenceClassification.from_pretrained(
            str(path), local_files_only=True, low_cpu_mem_usage=True,
        ).to(self.device).eval()
        self.max_length = min(int(self.tokenizer.model_max_length), 512)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rerank")

    async def rerank(
        self, query: str, documents: list[str], model: str, top_n: int | None = None,
    ) -> dict[str, Any]:
        if model != self.name:
            raise LookupError("本地重排模型不存在")
        if top_n is not None and top_n <= 0:
            raise ValueError("top_n 必须大于 0")
        return await asyncio.get_running_loop().run_in_executor(
            self.executor, self._score, query, documents, top_n,
        )

    def _score(self, query: str, documents: list[str], top_n: int | None) -> dict[str, Any]:
        import torch

        # 给正文保留至少半个窗口；超长问题截断仅影响评分，不改变检索和返回正文。
        query_ids = self.tokenizer.encode(
            query, add_special_tokens=False, truncation=True, max_length=self.max_length // 2,
        )
        width = self.max_length - len(query_ids) - self.tokenizer.num_special_tokens_to_add(pair=True)
        step = width - min(64, width // 4)
        scores = [0.0] * len(documents)
        batch: list[dict[str, Any]] = []
        owners: list[int] = []

        def score_batch() -> None:
            inputs = self.tokenizer.pad(batch, padding=True, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                values = self.model(**inputs).logits.reshape(-1).float().sigmoid().cpu().tolist()
            for index, value in zip(owners, values):
                scores[index] = max(scores[index], value)
            batch.clear()
            owners.clear()

        for index, document in enumerate(documents):
            tokens = self.tokenizer.encode(document, add_special_tokens=False, truncation=False, verbose=False)
            for start in range(0, max(1, len(tokens)), step):
                batch.append(self.tokenizer.prepare_for_model(
                    query_ids, tokens[start:start + width], add_special_tokens=True,
                    return_attention_mask=True, return_token_type_ids=False,
                ))
                owners.append(index)
                if len(batch) >= self.batch_size:
                    score_batch()
                if start + width >= len(tokens):
                    break
        if batch:
            score_batch()
        results = sorted(
            ({"index": index, "relevance_score": score} for index, score in enumerate(scores)),
            key=lambda item: item["relevance_score"], reverse=True,
        )
        return {"model": self.name, "results": results[:top_n]}

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.model = None
