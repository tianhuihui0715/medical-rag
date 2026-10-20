"""用户角色关联接口，提供分配、查询和解除关联功能。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.user_role_info import UserRoleCreate, UserRoleInfo
from service.user_role_service import UserRoleService

router = APIRouter(prefix="/user-role", tags=["用户角色"])


def get_service() -> UserRoleService:
    return UserRoleService()


@router.get("", response_model=list[UserRoleInfo], summary="查询用户角色关联")
def list_items(
    user_id: int | None = None,
    role_id: int | None = None,
    service: UserRoleService = Depends(get_service),
):
    return service.list_items(user_id, role_id)


@router.get("/{item_id}", response_model=UserRoleInfo, summary="查询关联详情")
def get_item(item_id: int, service: UserRoleService = Depends(get_service)):
    item = service.get(item_id)
    if item is None:
        raise HTTPException(404, "用户角色关联不存在")
    return item


@router.post("", response_model=UserRoleInfo, status_code=201, summary="分配用户角色")
def create_item(data: UserRoleCreate, service: UserRoleService = Depends(get_service)):
    return service.create(data)


@router.delete("/{item_id}", status_code=204, summary="解除用户角色关联")
def delete_item(item_id: int, service: UserRoleService = Depends(get_service)):
    if not service.delete(item_id):
        raise HTTPException(404, "用户角色关联不存在")
    return Response(status_code=204)
