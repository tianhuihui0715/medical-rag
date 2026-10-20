"""文件角色关联接口，提供授权、查询和解除授权功能。"""

from fastapi import APIRouter, Depends, HTTPException, Response

from model.file_role_info import FileRoleCreate, FileRoleInfo
from service.file_role_service import FileRoleService

router = APIRouter(prefix="/file-role", tags=["文件角色"])


def get_service() -> FileRoleService:
    return FileRoleService()


@router.get("", response_model=list[FileRoleInfo], summary="查询文件角色关联")
def list_items(
    file_id: int | None = None,
    role_id: int | None = None,
    service: FileRoleService = Depends(get_service),
):
    return service.list_items(file_id, role_id)


@router.get("/{item_id}", response_model=FileRoleInfo, summary="查询关联详情")
def get_item(item_id: int, service: FileRoleService = Depends(get_service)):
    item = service.get(item_id)
    if item is None:
        raise HTTPException(404, "文件角色关联不存在")
    return item


@router.post("", response_model=FileRoleInfo, status_code=201, summary="分配文件访问角色")
def create_item(data: FileRoleCreate, service: FileRoleService = Depends(get_service)):
    return service.create(data)


@router.delete("/{item_id}", status_code=204, summary="解除文件角色关联")
def delete_item(item_id: int, service: FileRoleService = Depends(get_service)):
    if not service.delete(item_id):
        raise HTTPException(404, "文件角色关联不存在")
    return Response(status_code=204)
