"""模型服务配置管理接口，响应中省略 API 密钥。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.model_provider_info import (
    ModelProviderCreate, ModelProviderRead, ModelProviderUpdate,
)
from service.model_provider_service import ModelProviderService

router = APIRouter(prefix="/model-provider", tags=["模型服务"])


def get_service() -> ModelProviderService:
    return ModelProviderService()


@router.get("", response_model=list[ModelProviderRead], summary="查询模型服务配置")
def list_providers(service: ModelProviderService = Depends(get_service)):
    return service.list_providers()


@router.get("/{provider_id}", response_model=ModelProviderRead, summary="查询模型服务详情")
def get_provider(provider_id: int, service: ModelProviderService = Depends(get_service)):
    item = service.get(provider_id)
    if item is None:
        raise HTTPException(404, "模型服务配置不存在")
    return item


@router.post("", response_model=ModelProviderRead, status_code=201, summary="新增模型服务")
def create_provider(data: ModelProviderCreate, service: ModelProviderService = Depends(get_service)):
    return service.create(data)


@router.put("/{provider_id}", response_model=ModelProviderRead, summary="修改模型服务")
def update_provider(
    provider_id: int, data: ModelProviderUpdate,
    service: ModelProviderService = Depends(get_service),
):
    item = service.update(provider_id, data)
    if item is None:
        raise HTTPException(404, "模型服务配置不存在")
    return item


@router.delete("/{provider_id}", status_code=204, summary="删除模型服务及所属模型")
def delete_provider(provider_id: int, service: ModelProviderService = Depends(get_service)):
    if not service.delete(provider_id):
        raise HTTPException(404, "模型服务配置不存在")
    return Response(status_code=204)
