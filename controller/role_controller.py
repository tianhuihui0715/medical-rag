"""角色管理接口，提供列表、详情及增删改操作。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.role_info import RoleCreate, RoleInfo, RoleUpdate
from service.role_service import RoleService

router = APIRouter(prefix="/role", tags=["角色"])


def get_service() -> RoleService:
    return RoleService()


@router.get("", response_model=list[RoleInfo], summary="查询角色列表")
def list_roles(service: RoleService = Depends(get_service)):
    return service.list_roles()


@router.get("/{role_id}", response_model=RoleInfo, summary="查询角色")
def get_role(role_id: int, service: RoleService = Depends(get_service)):
    item = service.get(role_id)
    if item is None:
        raise HTTPException(404, "角色不存在")
    return item


@router.post("", response_model=RoleInfo, status_code=201, summary="新增角色")
def create_role(data: RoleCreate, service: RoleService = Depends(get_service)):
    return service.create(data)


@router.put("/{role_id}", response_model=RoleInfo, summary="修改角色")
def update_role(
    role_id: int, data: RoleUpdate, service: RoleService = Depends(get_service)
):
    item = service.update(role_id, data)
    if item is None:
        raise HTTPException(404, "角色不存在")
    return item


@router.delete("/{role_id}", status_code=204, summary="删除角色及用户关联")
def delete_role(role_id: int, service: RoleService = Depends(get_service)):
    if not service.delete(role_id):
        raise HTTPException(404, "角色不存在")
    return Response(status_code=204)
