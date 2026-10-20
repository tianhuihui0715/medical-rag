"""模型管理与调用接口，支持聊天、向量化和重排，返回云端原始 JSON。"""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from model.model_info import (
    ChatRequest, EmbeddingRequest, ModelCreate, ModelInfo, ModelUpdate, RerankRequest,
)
from service.model_service import ModelService

router = APIRouter(prefix="/model", tags=["模型"])


def get_service() -> ModelService:
    return ModelService()


@router.get("", response_model=list[ModelInfo], summary="查询模型列表")
def list_models(
    provider_id: int | None = None, kind: str | None = None,
    service: ModelService = Depends(get_service),
):
    return service.list_models(provider_id, kind)


@router.get("/default/{kind}", response_model=ModelInfo, summary="查询某用途当前选中的模型")
def get_default(kind: str, service: ModelService = Depends(get_service)):
    item = service.get_default(kind)
    if item is None:
        raise HTTPException(404, "该用途尚未选择默认模型")
    return item


@router.put("/{model_id}/default", response_model=ModelInfo, summary="选为同用途的系统默认模型")
def set_default(model_id: int, service: ModelService = Depends(get_service)):
    try:
        item = service.set_default(model_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if item is None:
        raise HTTPException(404, "模型不存在")
    return item


@router.get("/{model_id}", response_model=ModelInfo, summary="查询模型详情")
def get_model(model_id: int, service: ModelService = Depends(get_service)):
    item = service.get(model_id)
    if item is None:
        raise HTTPException(404, "模型不存在")
    return item


@router.post("", response_model=ModelInfo, status_code=201, summary="新增模型")
def create_model(data: ModelCreate, service: ModelService = Depends(get_service)):
    return service.create(data)


@router.put("/{model_id}", response_model=ModelInfo, summary="修改模型")
def update_model(model_id: int, data: ModelUpdate, service: ModelService = Depends(get_service)):
    item = service.update(model_id, data)
    if item is None:
        raise HTTPException(404, "模型不存在")
    return item


@router.delete("/{model_id}", status_code=204, summary="删除模型")
def delete_model(model_id: int, service: ModelService = Depends(get_service)):
    if not service.delete(model_id):
        raise HTTPException(404, "模型不存在")
    return Response(status_code=204)


def _call(service: ModelService, model_id: int | None, kind: str, inputs: dict[str, Any]):
    """统一转换调用异常，避免把服务地址、密钥或上游响应正文返回给客户端。"""
    try:
        return service.call(model_id, kind, inputs)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except httpx.TimeoutException:
        raise HTTPException(504, "模型服务请求超时") from None
    except httpx.HTTPError:
        raise HTTPException(502, "模型服务调用失败") from None
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None


@router.post("/chat", summary="使用系统当前选中的聊天模型")
def chat_default(data: ChatRequest, service: ModelService = Depends(get_service)):
    return _call(service, None, "chat", data.model_dump())


@router.post("/embedding", summary="使用系统当前选中的向量模型")
def embed_default(data: EmbeddingRequest, service: ModelService = Depends(get_service)):
    return _call(service, None, "embedding", data.model_dump())


@router.post("/rerank", summary="使用系统当前选中的重排模型")
def rerank_default(data: RerankRequest, service: ModelService = Depends(get_service)):
    return _call(service, None, "rerank", data.model_dump(exclude_none=True))


@router.post("/{model_id}/chat", summary="调用聊天模型")
def chat(model_id: int, data: ChatRequest, service: ModelService = Depends(get_service)):
    return _call(service, model_id, "chat", data.model_dump())


@router.post("/{model_id}/embedding", summary="调用向量模型，支持单条或批量文本")
def embed(model_id: int, data: EmbeddingRequest, service: ModelService = Depends(get_service)):
    return _call(service, model_id, "embedding", data.model_dump())


@router.post("/{model_id}/rerank", summary="调用重排模型")
def rerank(model_id: int, data: RerankRequest, service: ModelService = Depends(get_service)):
    return _call(service, model_id, "rerank", data.model_dump(exclude_none=True))
