"""文件接口，上传时关联指定或默认知识库，并提供文件查询和处理任务提交。"""

from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from minio.error import MinioException
from sqlalchemy.exc import SQLAlchemyError
from urllib3.exceptions import HTTPError

from common.auth import get_current_user
from model.file_info import FileRead, FileUpload, ParseRequest
from model.chunk_info import SplitRequest
from model.user_info import UserInfo
from service.file_service import FileService
from service.split_service import SplitService

router = APIRouter(prefix="/file", tags=["文件"])


def get_service() -> FileService:
    return FileService()


def get_split_service() -> SplitService:
    return SplitService()


@router.get("", response_model=list[FileRead], summary="查询当前登录用户可检索的文件")
def list_files(
    user: UserInfo = Depends(get_current_user), service: FileService = Depends(get_service),
):
    try:
        return service.list_accessible_files(cast(int, user.id))
    except SQLAlchemyError:
        raise HTTPException(503, "数据库服务暂不可用") from None


@router.post("/split", status_code=202, summary="提交文件父子切块，支持单个或多个文件")
def start_split(
    data: SplitRequest,
    service: SplitService = Depends(get_split_service),
):
    try:
        return service.start_split(data.file_ids, data)
    except LookupError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "数据库服务暂不可用") from None


@router.post("/parse", status_code=202, summary="提交文件解析，支持单个或多个文件")
def start_parse(data: ParseRequest, service: FileService = Depends(get_service)):
    try:
        return service.start_parse(data.file_ids)
    except SQLAlchemyError:
        raise HTTPException(503, "数据库服务暂不可用") from None


@router.post("/upload", response_model=FileUpload, summary="上传文件")
def upload(
    file: UploadFile = File(...),
    source_path: str = Form(""),
    knowledge_id: int | None = Form(None, description="知识库 ID；省略时自动创建并复用默认知识库"),
    service: FileService = Depends(get_service),
):
    try:
        return service.upload(file, source_path, knowledge_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except (MinioException, HTTPError):
        raise HTTPException(503, "文件存储服务暂不可用") from None
    except SQLAlchemyError:
        raise HTTPException(503, "文件记录保存失败，已上传文件保留在临时桶中") from None


@router.post("/batch-upload", response_model=list[FileUpload], summary="批量上传文件")
def upload_many(
    files: list[UploadFile] = File(...),
    source_paths: list[str] | None = Form(None, description="与 files 按顺序对应；省略时使用文件名"),
    knowledge_id: int | None = Form(None, description="本批文件共用的知识库 ID；省略时使用默认知识库"),
    service: FileService = Depends(get_service),
):
    try:
        return service.upload_many(files, source_paths, knowledge_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except (MinioException, HTTPError):
        raise HTTPException(503, "文件存储服务暂不可用") from None
    except SQLAlchemyError:
        raise HTTPException(503, "文件记录保存失败，已上传文件保留在临时桶中") from None
