"""权限角色关联接口，提供分配、查询和解除关联功能。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.permission_role_info import PermissionRoleCreate, PermissionRoleInfo
from service.permission_role_service import PermissionRoleService

router = APIRouter(prefix="/permission-role", tags=["权限角色"])


def get_service() -> PermissionRoleService:
    return PermissionRoleService()


@router.get("", response_model=list[PermissionRoleInfo], summary="查询权限角色关联")
def list_items(
    permission_id: int | None = None,
    role_id: int | None = None,
    service: PermissionRoleService = Depends(get_service),
):
    return service.list_items(permission_id, role_id)


@router.get("/{item_id}", response_model=PermissionRoleInfo, summary="查询关联详情")
def get_item(item_id: int, service: PermissionRoleService = Depends(get_service)):
    item = service.get(item_id)
    if item is None:
        raise HTTPException(404, "权限角色关联不存在")
    return item


@router.post("", response_model=PermissionRoleInfo, status_code=201, summary="分配角色权限")
def create_item(data: PermissionRoleCreate, service: PermissionRoleService = Depends(get_service)):
    return service.create(data)


@router.delete("/{item_id}", status_code=204, summary="解除权限角色关联")
def delete_item(item_id: int, service: PermissionRoleService = Depends(get_service)):
    if not service.delete(item_id):
        raise HTTPException(404, "权限角色关联不存在")
    return Response(status_code=204)
