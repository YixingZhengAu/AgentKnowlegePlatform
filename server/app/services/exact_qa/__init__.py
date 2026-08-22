"""精准问答域(S1)。

本包被 import 时完成**本域的注册副作用**:
`publisher.py` 里的 `@register_publisher("qa_pair")` 必须在发布骨架调它之前进注册表,
而 Job 子类的注册由 `app/services/__init__.py` 的那一行 `import ... ingest` 触发
(全局唯一注册点,见 DOMAIN-DEV-GUIDE §5 冲突地图)。

放在这里而不是让 `services/__init__.py` 多写一行:publisher 是本域内部的事,
共享文件上只留 Job 那一行,并行开发时冲突面最小。
"""

from app.services.exact_qa import publisher  # noqa: F401  注册 qa_pair 的 publisher
