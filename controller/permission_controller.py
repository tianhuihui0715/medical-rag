"""权限管理接口，提供列表、详情及增删改操作。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.permission_info import PermissionCreate, PermissionInfo, PermissionUpdate
from service.permission_service import PermissionService

router = APIRouter(prefix="/permission", tags=["权限"])


def get_service() -> PermissionService:
    return PermissionService()


@router.get("", response_model=list[PermissionInfo], summary="查询权限列表")
def list_permissions(service: PermissionService = Depends(get_service)):
    return service.list_permissions()


@router.get("/{permission_id}", response_model=PermissionInfo, summary="查询权限")
def get_permission(permission_id: int, service: PermissionService = Depends(get_service)):
    item = service.get(permission_id)
    if item is None:
        raise HTTPException(404, "权限不存在")
    return item


@router.post("", response_model=PermissionInfo, status_code=201, summary="新增权限")
def create_permission(data: PermissionCreate, service: PermissionService = Depends(get_service)):
    return service.create(data)


@router.put("/{permission_id}", response_model=PermissionInfo, summary="修改权限")
def update_permission(
    permission_id: int, data: PermissionUpdate,
    service: PermissionService = Depends(get_service),
):
    item = service.update(permission_id, data)
    if item is None:
        raise HTTPException(404, "权限不存在")
    return item


@router.delete("/{permission_id}", status_code=204, summary="删除权限及关联")
def delete_permission(permission_id: int, service: PermissionService = Depends(get_service)):
    if not service.delete(permission_id):
        raise HTTPException(404, "权限不存在")
    return Response(status_code=204)
