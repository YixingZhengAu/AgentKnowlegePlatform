"""导出 openapi.json(make types 的第一步)。

契约先行:前端类型由这份 schema 生成,不允许手写。
用法:uv run python -m scripts.dump_openapi ../web/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[openapi] {out.resolve()}  paths={len(schema.get('paths', {}))}")


if __name__ == "__main__":
    main()
