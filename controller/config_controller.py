"""配置管理接口，提供列表、详情及增删改操作。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.config_info import ConfigCreate, ConfigInfo, ConfigUpdate
from service.config_service import ConfigService

router = APIRouter(prefix="/config", tags=["配置"])


def get_service() -> ConfigService:
    return ConfigService()


@router.get("", response_model=list[ConfigInfo], summary="查询配置列表")
def list_configs(
    category: str | None = None, service: ConfigService = Depends(get_service)
):
    return service.list_configs(category)


@router.get("/key/{key}", response_model=ConfigInfo, summary="按键查询配置")
def get_config_by_key(key: str, service: ConfigService = Depends(get_service)):
    item = service.get_by_key(key)
    if item is None:
        raise HTTPException(404, "配置不存在")
    return item


@router.get("/{config_id}", response_model=ConfigInfo, summary="查询配置")
def get_config(config_id: int, service: ConfigService = Depends(get_service)):
    item = service.get(config_id)
    if item is None:
        raise HTTPException(404, "配置不存在")
    return item


@router.post("", response_model=ConfigInfo, status_code=201, summary="新增配置")
def create_config(data: ConfigCreate, service: ConfigService = Depends(get_service)):
    try:
        return service.create(data)
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from None


@router.put("/{config_id}", response_model=ConfigInfo, summary="修改配置")
def update_config(
    config_id: int, data: ConfigUpdate, service: ConfigService = Depends(get_service)
):
    item = service.update(config_id, data)
    if item is None:
        raise HTTPException(404, "配置不存在")
    return item


@router.delete("/{config_id}", status_code=204, summary="删除配置")
def delete_config(config_id: int, service: ConfigService = Depends(get_service)):
    if not service.delete(config_id):
        raise HTTPException(404, "配置不存在")
    return Response(status_code=204)
