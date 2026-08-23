# claude.md(data · 测试用示例数据)

**职责**:存放用于开发/演示的示例原料(测试上传、跑通文档 RAG 流水线用),不参与运行时代码。

| 文件 | 说明 |
| --- | --- |
| `generate_sample_pdfs.py` | 生成下面两份 PDF 的脚本(reportlab + pillow,ephemeral 依赖,不入项目依赖) |
| `company-travel-policy.pdf` | 示例政策文档,5 页,含 6 张表 + 3 张图(横幅/柱状图/流程图) |
| `company-it-policy.pdf` | 示例政策文档,5 页,含 7 张表 + 3 张图(横幅/分层图/柱状图) |

重新生成:`uv run --with reportlab --with pillow python data/generate_sample_pdfs.py`

详见 `data/architect.md`。
