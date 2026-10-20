"""FastAPI 应用入口，注册路由并管理启动校验和连接资源的生命周期。"""

from contextlib import ExitStack, asynccontextmanager

from fastapi import FastAPI

from clint.minio_connection import get_minio_connection
from clint.model_connection import get_model_connection
from clint.milvus_connection import get_milvus_connection
from clint.mysql_connection import get_mysql_connection
from clint.redis_connection import get_redis_connection
from common.router import Router
from common.config.config_validator import ConfigValidator
from service.embedding_service import EmbeddingService
from service.rerank_service import RerankService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时校验配置，退出时按逆序释放模型及各存储连接资源。"""
    with ExitStack() as resources:
        db = get_mysql_connection()
        resources.callback(db.close)
        ConfigValidator().validate()
        minio = get_minio_connection()
        resources.callback(minio.close)
        redis = get_redis_connection()
        resources.callback(redis.close)
        model = get_model_connection()
        resources.callback(model.close)
        milvus = get_milvus_connection()
        resources.callback(milvus.close)
        # 单应用进程只加载一份本地模型，队列任务通过向量接口复用。
        app.state.embedding = EmbeddingService()
        resources.callback(app.state.embedding.close)
        app.state.rerank = RerankService()
        resources.callback(app.state.rerank.close)
        yield


app = FastAPI(lifespan=lifespan)
app.include_router(Router())
