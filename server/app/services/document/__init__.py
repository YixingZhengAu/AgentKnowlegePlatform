"""文档 RAG 域。

这里只做一件事:import `publisher` 触发 `@register_publisher("chunk")`。
Job 的注册在 `app/services/__init__.py`(全局唯一注册点)。
"""

from app.services.document import publisher  # noqa: F401  注册 chunk 的 publisher
