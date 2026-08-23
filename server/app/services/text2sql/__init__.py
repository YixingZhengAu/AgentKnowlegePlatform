"""智能问数域。

本文件只做一件事:import `publisher`,触发 `@register_publisher("sql_intent")`。
Job 的注册行在 `app/services/__init__.py`(全局唯一注册点)。
"""

from app.services.text2sql import publisher  # noqa: F401  注册 sql_intent 的 publisher
