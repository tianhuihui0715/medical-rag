"""模型服务配置列表查询，使用业务层传入的会话。"""

from sqlmodel import Session, col, select

from model.model_provider_info import ModelProviderInfo


def list_providers(session: Session) -> list[ModelProviderInfo]:
    query = select(ModelProviderInfo).order_by(col(ModelProviderInfo.id))
    return list(session.exec(query).all())
