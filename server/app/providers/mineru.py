"""MinerU 文档解析服务的 HTTP 客户端(契约变更 C3,S2 上提)。

**为什么在 providers/ 而不在某个域里**:它是全项目唯一的 PDF 解析入口 ——
S1(精准问答)与 S2(文档 RAG)都要调它。原来住在 `services/exact_qa/parser.py`,
S2 要用就得跨域 import,违反"域与域互不 import"的纪律,所以上提到供应商层。
**行为与迁移前逐字相同**,只是换了住址。

形态:**HTTP 调常驻 mineru-api 容器**(S1 Step 0 实测结论)。
为什么不用 CLI:3.4.5 的 CLI 内部本就是起一个临时 mineru-api 再打自己,
每次调用白付 ~13s 模型加载(实测 CLI 热跑 32s vs 常驻服务 17.7s)。
好处还有一个:MinerU 那 4.9GB 依赖树永远不进 server 的镜像。
"""

import json
from pathlib import Path

import httpx

from app.config import settings
from app.core.errors import ProviderError


async def call_mineru(pdf: Path) -> dict:
    """POST /file_parse,一次拿回 md / content_list / middle_json / images。

    只开我们需要的四个开关:model_output 与 original_file 体积大且没用。

    Args:
        pdf: 本地 PDF 路径。

    Returns:
        单文件的解析结果(已剥掉外层 results 字典,下游不必再剥一层)。

    Raises:
        ProviderError: 服务不可用(`mineru_unavailable`)、解析报错(`mineru_failed`)
            或返回空结果(`mineru_empty`)。
    """
    url = f"{settings.mineru_api_url.rstrip('/')}/file_parse"
    data = {
        "backend": "pipeline",         # 3.4.5 默认已是 hybrid-engine,必须显式指定
        "parse_method": "auto",
        "formula_enable": "true",
        "table_enable": "true",
        "return_md": "true",
        "return_content_list": "true",
        "return_middle_json": "true",  # 只为拿每页 page_size(PDF point)
        "return_images": "true",
        "return_model_output": "false",
        "return_original_file": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.mineru_timeout_sec) as client:
            with pdf.open("rb") as fh:
                resp = await client.post(
                    url, data=data, files={"files": (pdf.name, fh, "application/pdf")}
                )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        # 报错要能直接指向"容器没起来",否则一眼看不出是服务问题还是文档问题
        raise ProviderError(
            f"MinerU 解析服务不可用({url}):{type(exc).__name__}: {exc}。"
            "起法:make mineru(定义在 docker/mineru + 根 docker-compose.yml)。",
            code="mineru_unavailable",
        ) from exc

    body = resp.json()
    if body.get("error"):
        raise ProviderError(f"MinerU 解析失败:{body['error']}", code="mineru_failed")
    results = body.get("results") or {}
    if not results:
        raise ProviderError(
            f"MinerU 返回空 results:{json.dumps(body)[:300]}", code="mineru_empty"
        )
    # 单文件上传,取第一个(key 是去掉扩展名的文件名)
    return next(iter(results.values()))


def as_json(value: object) -> object:
    """`/file_parse` 把 content_list / middle_json 以 **JSON 字符串** 回传(实测),
    CLI 落盘的是对象 —— 这里统一成对象,免得下游两套写法。"""
    return json.loads(value) if isinstance(value, str) else value
