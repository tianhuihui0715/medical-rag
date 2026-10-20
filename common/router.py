"""汇总各业务模块路由，供应用入口统一注册。"""

from fastapi import APIRouter

from controller.config_controller import router as config_router
from controller.dict_controller import router as dict_router
from controller.embedding_controller import router as embedding_router
from controller.file_controller import router as file_router
from controller.file_role_controller import router as file_role_router
from controller.model_controller import router as model_router
from controller.model_provider_controller import router as model_provider_router
from controller.permission_controller import router as permission_router
from controller.permission_role_controller import router as permission_role_router
from controller.permission_user_controller import router as permission_user_router
from controller.role_controller import router as role_router
from controller.rerank_controller import router as rerank_router
from controller.search_controller import router as search_router
from controller.user_controller import router as user_router
from controller.user_role_controller import router as user_role_router


class Router(APIRouter):
    """集中注册各模块的接口路由。"""
    def __init__(self):
        super().__init__()
        self.include_router(file_router)
        self.include_router(file_role_router)
        self.include_router(config_router)
        self.include_router(dict_router)
        self.include_router(user_router)
        self.include_router(role_router)
        self.include_router(user_role_router)
        self.include_router(permission_router)
        self.include_router(permission_role_router)
        self.include_router(permission_user_router)
        self.include_router(model_provider_router)
        self.include_router(model_router)
        self.include_router(embedding_router)
        self.include_router(rerank_router)
        self.include_router(search_router)
