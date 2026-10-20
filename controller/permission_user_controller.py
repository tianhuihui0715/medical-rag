"""权限用户关联接口，提供分配、查询和解除关联功能。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.permission_user_info import PermissionUserCreate, PermissionUserInfo
from service.permission_user_service import PermissionUserService

router = APIRouter(prefix="/permission-user", tags=["权限用户"])


def get_service() -> PermissionUserService:
    return PermissionUserService()


@router.get("", response_model=list[PermissionUserInfo], summary="查询权限用户关联")
def list_items(
    permission_id: int | None = None,
    user_id: int | None = None,
    service: PermissionUserService = Depends(get_service),
):
    return service.list_items(permission_id, user_id)


@router.get("/{item_id}", response_model=PermissionUserInfo, summary="查询关联详情")
def get_item(item_id: int, service: PermissionUserService = Depends(get_service)):
    item = service.get(item_id)
    if item is None:
        raise HTTPException(404, "权限用户关联不存在")
    return item


@router.post("", response_model=PermissionUserInfo, status_code=201, summary="分配用户权限")
def create_item(data: PermissionUserCreate, service: PermissionUserService = Depends(get_service)):
    return service.create(data)


@router.delete("/{item_id}", status_code=204, summary="解除权限用户关联")
def delete_item(item_id: int, service: PermissionUserService = Depends(get_service)):
    if not service.delete(item_id):
        raise HTTPException(404, "权限用户关联不存在")
    return Response(status_code=204)
