"""业务逻辑层(分知识域)。

本文件是全局唯一的「Job 注册 import 点」:Job 子类靠 import 副作用
写入 core/jobs.py 的注册表,注册行只允许出现在这里。
api/jobs.py 只 `import app.services`,不直接 import 任何具体域。

S1–S3 各域的 Job 子类就绪后,在下面各加一行 import。
"""

from app.core import jobs_demo  # noqa: F401  框架联调假任务 demo_sleep
from app.services.exact_qa import ingest  # noqa: F401  qa_parse / qa_extract
# S2:from app.services.document import ingest  # noqa: F401
# S3:from app.services.text2sql import ingest  # noqa: F401
