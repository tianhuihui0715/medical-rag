"""字典管理接口，提供列表、详情及增删改操作。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.dict_info import DictCreate, DictInfo, DictUpdate
from service.dict_service import DictService

router = APIRouter(prefix="/dict", tags=["字典"])


def get_service() -> DictService:
    return DictService()


@router.get("", response_model=list[DictInfo], summary="查询同级字典项")
def list_items(
    dict_type: str,
    parent_id: int | None = None,
    service: DictService = Depends(get_service),
):
    return service.list_items(dict_type, parent_id)


@router.get("/{item_id}", response_model=DictInfo, summary="查询字典项")
def get_item(item_id: int, service: DictService = Depends(get_service)):
    item = service.get(item_id)
    if item is None:
        raise HTTPException(404, "字典项不存在")
    return item


@router.post("", response_model=DictInfo, status_code=201, summary="新增字典项")
def create_item(data: DictCreate, service: DictService = Depends(get_service)):
    return service.create(data)


@router.put("/{item_id}", response_model=DictInfo, summary="修改字典项")
def update_item(
    item_id: int, data: DictUpdate, service: DictService = Depends(get_service)
):
    item = service.update(item_id, data)
    if item is None:
        raise HTTPException(404, "字典项不存在")
    return item


@router.delete("/{item_id}", status_code=204, summary="删除字典项")
def delete_item(item_id: int, service: DictService = Depends(get_service)):
    if not service.delete(item_id):
        raise HTTPException(404, "字典项不存在")
    return Response(status_code=204)
