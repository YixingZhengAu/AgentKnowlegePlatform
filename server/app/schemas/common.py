"""跨模块共用的 Pydantic schema。"""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """从 SQLAlchemy 对象直接序列化的基类。"""

    model_config = ConfigDict(from_attributes=True)


class ListResponse[T](BaseModel):
    """列表统一包一层,后续加分页不破坏契约。"""

    items: list[T]
    total: int


class HealthResponse(BaseModel):
    status: str
    env: str
    database: str
    database_error: str | None = None
    embedding_dim: int
