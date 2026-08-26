"""预下载重排模型权重(装机一次性步骤,由 bootstrap.sh 调用)。

**为什么要单独一步**:`sentence-transformers` 每次加载都会去 HuggingFace 核对版本,
哪怕权重早就缓存在本地 —— 实测这一趟网络往返要 **8.6 秒**,把 3 秒的加载拖成 13 秒。
所以运行时一律 `HF_HUB_OFFLINE=1` 强制走本地缓存,**代价是权重必须先下好**。
这正是 bootstrap 的职责:一次性步骤在装机时做完,不留给第一个用户请求。

跑法:
    cd server && uv run python -m scripts.fetch_rerank_model
"""

import os
import sys
import time

# 这一步就是要联网下载,必须显式关掉离线模式(用户 .env 里通常开着)
os.environ["HF_HUB_OFFLINE"] = "0"

from app.config import settings  # noqa: E402 环境变量要先于 HF 相关 import 设好


def main() -> None:
    """把权重拉到本地缓存;已缓存则秒过。

    Raises:
        SystemExit: 下载失败时退出码 1,并给出可操作的提示。
    """
    name = settings.doc_rag_rerank_model
    print(f"预下载重排模型:{name}(约 90MB,已缓存则秒过)")
    started = time.monotonic()
    try:
        from sentence_transformers import CrossEncoder

        CrossEncoder(name, max_length=512)
    except Exception as exc:  # noqa: BLE001 装机脚本要把话说清楚
        print(f"下载失败:{exc}", file=sys.stderr)
        print(
            "检查网络或代理后重跑;若长期无外网,把 .env 的 "
            "DOC_RAG_RERANK_OFFLINE 关掉并改用 RERANK_PROVIDER=passthrough。",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    print(f"就绪,用时 {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
