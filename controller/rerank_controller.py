"""提供本地重排模型接口，供统一模型服务和检索流程复用。"""

from typing import cast

from fastapi import APIRouter, HTTPException, Request

from model.model_info import LocalRerankRequest
from service.rerank_service import RerankService

router = APIRouter(prefix="/v1", tags=["本地重排"])


@router.post("/rerank", summary="调用本地 BGE 重排模型")
async def rerank_local(data: LocalRerankRequest, request: Request):
    service = cast(RerankService, request.app.state.rerank)
    try:
        return await service.rerank(data.query, data.documents, data.model, data.top_n)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
