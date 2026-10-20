"""提供当前登录用户的统一检索接口，返回去重并重排后的父块。"""

from typing import cast

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pymilvus import MilvusException
from sqlalchemy.exc import SQLAlchemyError

from common.auth import get_current_user
from model.search_info import DirectorySearchRequest, SearchRequest, SearchResult
from model.user_info import UserInfo
from service.search_service import SearchService

router = APIRouter(prefix="/search", tags=["检索"])


def get_service() -> SearchService:
    return SearchService()


@router.post("", response_model=SearchResult, summary="按知识库和角色权限检索前 K 个父块")
def search(
    data: SearchRequest, user: UserInfo = Depends(get_current_user),
    service: SearchService = Depends(get_service),
):
    return _search(data, user, service)


@router.post("/directory", response_model=SearchResult, summary="按部门和职位检索目录内前 K 个父块")
def search_directory(
    data: DirectorySearchRequest, user: UserInfo = Depends(get_current_user),
    service: SearchService = Depends(get_service),
):
    return _search(data, user, service)


def _search(data: SearchRequest | DirectorySearchRequest, user: UserInfo, service: SearchService):
    """复用检索调用及异常响应。"""
    try:
        return service.search(data, cast(int, user.id))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except LookupError as exc:
        raise HTTPException(400, str(exc)) from None
    except httpx.TimeoutException:
        raise HTTPException(504, "模型服务请求超时") from None
    except httpx.HTTPError:
        raise HTTPException(502, "模型服务调用失败") from None
    except (MilvusException, SQLAlchemyError):
        raise HTTPException(503, "检索存储服务暂不可用") from None
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None
