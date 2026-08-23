# architect.md(data)

## 1. 这些文件是干什么的

两份 PDF 是**测试原料**,不是项目文档:用来验证文档解析 / 分块 / 向量化 / 引用定位这条链路
——它们刻意做成"真实企业政策"的形态:多页、跨页表格、正文段落、位图插图、页眉页脚与页码。
正文全英文(对外可见内容,遵循根 `CLAUDE.md` 语言纪律),公司背景统一用 Clenergy Australia Pty Ltd。

两份文档各 5 页,结构对称,便于做对比测试:

| | company-travel-policy.pdf | company-it-policy.pdf |
| --- | --- | --- |
| 文档编号 | CLE-HR-TRV-004 | CLE-IT-POL-011 |
| 表格 | 文档控制 / 审批阈值 / 差旅补贴上限 / 报销凭证 / 紧急联系人 / FAQ | 文档控制 / 设备标准 / 账号口令 / 事件分级 / 数据分级 / 软件与 AI 工具 |
| 图片 | 封面横幅、FY2025 费用柱状图、审批流程图 | 封面横幅、权限分层图、FY2025 安全事件柱状图 |
| 适合测什么 | 数值型问答(上限、阈值、天数)、跨页表格切分 | 分级/枚举型问答、条目式列表抽取 |

数据全部虚构,不含任何真实客户或个人信息。

## 2. generate_sample_pdfs.py 的结构

自上而下四段,改内容时只需动第三段:

1. **常量与字体**:配色(NAVY / ACCENT / LIGHT)、macOS 系统字体路径,取不到时退回 Pillow 默认字体。
2. **图片生成(Pillow)**:`make_banner` 渐变横幅、`make_bar_chart` 柱状图、`make_flow` 横向流程图、
   `make_layers` 权限分层图。都返回临时目录里的 PNG 路径,PDF 生成完即可丢弃。
3. **PDF 构件与内容**:`table()` / `bullets()` / `picture()` 是排版辅助;
   `travel_story()` 与 `it_story()` 各自返回一个 reportlab flowable 列表 —— **文案与表格数据都在这两个函数里**,
   页与页之间用 `PageBreak()` 硬分隔,所以页数是确定的 5 页(改内容后要确认没把某页撑到溢出)。
4. **输出**:`build()` 统一页边距、页眉页脚(页码固定写 "of 5")与 PDF 元数据,写到 `data/` 下。

依赖用 `uv run --with reportlab --with pillow` 临时注入,**不要 `uv add`** —— 生成器是一次性工具,
不该让后端运行时背上 reportlab/pillow。

## 3. 校验

改完重新生成后,确认页数仍是 5:

```bash
python3 -c "import re;d=open('data/company-it-policy.pdf','rb').read();print(len(re.findall(rb'/Type\s*/Page[^s]',d)))"
```
