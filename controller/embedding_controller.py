"""提供本地模型向量接口，供队列及统一模型调用流程访问。"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from model.model_info import LocalEmbeddingRequest
from service.embedding_service import EmbeddingService

router = APIRouter(prefix="/v1", tags=["本地向量"])


@router.post("/embeddings", summary="调用本地模型，返回稠密及稀疏向量")
async def embed_local(data: LocalEmbeddingRequest, request: Request):
    service = cast(EmbeddingService, request.app.state.embedding)
    texts = [data.input] if isinstance(data.input, str) else data.input
    try:
        return await service.embed(texts, data.model)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
