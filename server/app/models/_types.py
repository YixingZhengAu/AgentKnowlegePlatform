"""模型层共用的列类型。"""

from pgvector.sqlalchemy import Vector

from app.config import settings


def embedding_column_type() -> Vector:
    """向量列维度由 EMBEDDING_DIM 决定,不硬编码(换供应商=换维度=重建列)。"""
    return Vector(settings.embedding_dim)
