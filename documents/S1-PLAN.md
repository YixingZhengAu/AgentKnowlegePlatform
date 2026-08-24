# S1 精准问答模块 —— 开发计划

> 本文是 S1 的开发计划与实施记录(Step 8 完成后归档到此)。
> ⚠ **文中出现的 `tmp/s1-dev/` 沙箱路径都是历史叙述**:沙箱是 S1 的一次性开发脚手架,
> 功能全部集成进 `server/`、`web/` 之后已整目录删除;沙箱里的实测结论都已抄进本文,
> 需要留下的输入文件搬到了 `server/scripts/fixtures/`,MinerU 容器定义搬到了 `docker/mineru/`。
> 逐 stage 的自测流水记录(临时性文档)也随之删除,结论保留在本文各 Step 的 ✅ 段落里。
> 背景:方案吸收了对参考平台「企业问答知识」模块的实测调研结论(调研原始材料已清理),按我们的场景裁剪:无目录树、无审批流、无安全等级,**采纳即发布**。

---

## 1. 目标与完成标准

S1 交付精准问答的完整闭环:**上传 PDF → MinerU 解析 → 人工校对解析文本 → LLM 抽取候选 QA → 人工采纳(采纳即发布)→ 问答命中返回标准答案**。

**DoD(可当场演示)**:从浏览器上传一份 PDF,校对解析文本后触发抽取,在审核台采纳若干条 QA,随后在对话里提问能命中并返回标准答案,标注 "Verified Answer"。

> 相比 PRD §9.6 原 S1 DoD 新增了"校对解析文本"环节,归档时同步 PRD。

---

## 2. 测试数据(开发期统一用这一份)

**`server/scripts/fixtures/sample-paper-3p.pdf`**(沙箱时期在 `tmp/`)—— YOLOv3 论文(arXiv:1804.02767)前 3 页截取,约 1.4MB。选它是因为 3 页里图、表、公式齐全,能全面检验解析与抽取:

| 页 | 内容 |
|---|---|
| 第 1 页 | 标题/摘要/正文 + **Figure 1**(mAP-推理耗时对比图,矢量图,内嵌小型数据表) |
| 第 2 页 | **Figure 2**(bounding box 示意图)+ **Table 1**(Darknet-53 网络结构表)+ 数学公式 |
| 第 3 页 | **Table 2**(backbone 对比表)+ **Table 3**(COCO 结果表,大表) |

**开发纪律:M1–M5 所有模块的开发与调优一律以这份 PDF 为输入**,产物(解析 md、候选 QA json 等)沉淀在 `tmp/s1-dev/out/` 供下游模块直接取用。到端到端阶段(Step 8)再换虚构的业务手册演示。抽取效果的直观自检问题如:"What backbone does YOLOv3 use?"、"How many convolutional layers does Darknet-53 have?"。

---

## 3. 开发纪律:tmp 沙箱先行,验证通过才集成 ★

**所有 S1 代码先写在 `tmp/s1-dev/` 里,与正式代码库完全隔离;直到全部功能模块在命令行里验证通过,才开始集成进 `server/` 和 `web/`。**

沙箱阶段的硬规则:

1. **独立存在,零依赖原有项目**:`tmp/s1-dev/` 是一个自带 `pyproject.toml` 的独立 uv 项目(`uv init`),**不 import `server/` 任何代码、不连项目数据库、不改动 `server/`、`web/`、`documents/` 的任何文件**。
2. **LLM 调用直接用 openai SDK**:读根目录 `.env` 里的 key(只读),不走 server 的 Provider 层——Provider 层是集成阶段才替换进去的。
3. **检索验证不碰 pgvector**:用内存向量(numpy 余弦)调阈值和召回效果;pgvector 写入属于集成阶段的机械劳动,不影响效果结论。
4. **模块间以文件交接**:parse 产出 md → 人肉校对 md → extract 产出 qa.json → similar 补全 → retrieve 读 qa.json 建内存索引。每个模块可独立重跑。
5. **集成门槛(gate)**:`parse → 校对 → extract → similar → retrieve` 全链路 CLI 走通、每个模块的输出质量满意(解析可读、候选 QA 准确带引用、相似问自然、检索阈值可区分命中/未命中)之后,才允许动正式代码库。集成时把纯函数平移进 `server/app/services/exact_qa/`,替换 openai 直调为 Provider 层、内存索引为 pgvector,逻辑本身不再改。

沙箱目录规划:

```
tmp/
├─ sample-paper-3p.pdf     # 测试数据(§2)
└─ s1-dev/                 # 沙箱项目(独立 uv 项目)
   ├─ pyproject.toml        # 独立 uv 项目(pydantic/openai/numpy/httpx/python-dotenv)
   ├─ docker/               # MinerU 容器(Dockerfile + compose;Step 0 已建)
   ├─ schemas.py           # ★ 数据契约唯一出处:产物文件名常量 + 图片 URL 方案 +
   │                       #   ContentBlock/ParseResult/OriginRef/QaCandidate/检索模型(Step 1 已建)
   ├─ check_contract.py    # Step 1 验收:用真实 MinerU 产物校验契约
   ├─ parse_pdf.py         # M1:HTTP 调常驻 mineru-api
   ├─ extract_qa.py        # M2:LLM 抽取候选 QA
   ├─ gen_similar.py       # M3:相似问题生成
   ├─ retrieve_qa.py       # M4:embedding + 内存余弦检索 + 命中三段式判定
   ├─ eval_questions.json  # M4 评测集(真实问法 / 越界 / 同领域无答案的困难负例)
   ├─ out/                 # 各步产物:MinerU 产物目录、reviewed.md、qa.json、实测记录
   └─ notes/               # MinerU 实测记录等
```

---

## 4. 上传者旅程(5 步、2 道人工关)

```
第1步 上传:拖入 PDF(S1 仅支持 PDF)→ 提交,创建解析 Job
      ↓ 机器时间
第2步 自动解析:MinerU 把 PDF 解析为 Markdown(+图片)
      文档状态:已上传 → 解析中 → 待校对(失败可重跑)

第3步 解析校对(第一道人工关):进入校对页
      ┌────────────────┬────────────────────┐
      │ 左:原 PDF 预览   │ 右:解析 Markdown(可编辑)│
      └────────────────┴────────────────────┘
      左右对照检查解析质量;右侧可修改文本、删除无用内容
      (页眉页脚/乱码/无关段落)。编辑完点「确认,开始抽取」
      ★ 后续抽取用的是校对后的文本
      ↓ 机器时间
第4步 自动抽取:LLM 从校对后文本抽取候选 QA,创建抽取 Job
      文档状态:抽取中 → 待采纳(失败可重跑)
      ★ 候选 QA 硬性要求:答案非空 + 必须带原文参考(出处引用),
        不满足的在抽取阶段直接过滤,不进入候选列表

第5步 QA 采纳(第二道人工关):候选 QA 审核台,逐条(可批量):
        左 = 原文参考(该 QA 引用的原文片段,对照校验)
        中 = 问题 + 答案(可修改)
        右 = 相似问题(改写问法,可增删改,用于扩召回)
      裁决「采纳」或「不采纳」
      ★ 采纳即发布:点采纳瞬间写入正式表 + 生成向量索引
        (标准问 + 每条相似问各 embedding 一行),立即参与检索
      没有目录前置、没有发布申请、没有审批、没有"待发布"中间态
```

**状态机(裁剪到最薄)**

- 文档:`已上传 → 解析中 → 待校对 →(用户确认)→ 抽取中 → 待采纳 → 已完成`,解析/抽取失败态可重跑。
- 候选 QA:`待采纳 → 已采纳(=已发布,在库有索引可检索)/ 不采纳(留痕不入库)`。
- 后续如需"下线",给已采纳条目加一个下线动作(置 disabled + 删向量)即可,不引入更多状态。

**保留的关键设计决策**(调研消化后确定为我们自己的做法):

1. 候选与正式分离:抽取产物进 `staging_items`,采纳才进 `exact_qa_items`;
2. 相似问法扩召回:每条 QA 的召回面 = 标准问 + 相似问,各自独立 embedding(精准 QA 命中率的核心手段);
3. 只检索"已采纳"的知识:采纳 = 写向量索引,索引里有的才可能被命中;
4. 漏斗计数:文档行显示"抽取 N 条 / 已采纳 M 条",一眼看到知识转化率;
5. 列表轻详情重:候选/正式 QA 列表接口不带长答案正文,详情单独拉。

---

## 5. 核心功能模块拆分 ★

每个模块是一个**独立的开发 step**,各自有 CLI 入口、独立验证,不合并。任何一个模块效果不行(解析烂 / 抽取质量差 / 召回不准),都能单独定位、单独调优。每个模块写明两个落点:**沙箱落点**(现在写在哪)和**集成落点**(验证通过后搬到哪)。

### M1 文档解析(MinerU 3.4.5,pipeline 模式,Docker 本地部署)★ Step 0 已实测

- 输入:PDF 文件路径;输出:markdown + content_list + 图片。
- **本地部署方式:Docker 自建镜像**(实测结论,见下):
  - 官方镜像基于 CUDA+sglang(amd64),Apple Silicon 不可用 → 自建 `docker/mineru/Dockerfile`(沙箱时期在 `tmp/s1-dev/docker/`),
    base `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`。
  - **只装 `mineru[pipeline]==3.4.5` 并补装 `six`**(3.4.5 漏写的依赖,不补必崩);
    **绝不能装 `mineru[all]`** —— linux 上会拉 vllm(CUDA/amd64)必然失败。
  - 实测资源:镜像构建 5min15s(site-packages 4.9GB)、模型权重自动下载 42s / **1.0GB**、
    解析峰值内存 **2.4GB**。(计划早期写的"20GB 权重 / 16GB 内存"是 VLM 后端的量级,不适用。)
  - 参数修正:3.4.5 **没有 `--lang en`**(枚举里只有 ch/korean/arabic/… ,英文用默认 `ch` 即可);
    默认 backend 已变成 `hybrid-engine`,**必须显式 `-b pipeline`**。标准调用
    `mineru -p <pdf> -o <dir> -b pipeline -m auto`。
- **集成形态:常驻 `mineru-api` 容器 + HTTP 调用**(实测后从 subprocess CLI 改过来):
  - 3.4.5 的 CLI 内部本就是起一个临时 mineru-api 再打自己,所以 CLI 每次调用都白付 ~13s 模型加载。
  - 实测 3 页 PDF:CLI 冷启 73s / CLI 热跑 32s / **常驻服务后续请求 17.7s(≈6s 每页,CPU)**。
  - `POST /file_parse`(同步,我们用这个)返回 `results[文件名].{md_content, content_list, images}`,
    **images 是 `{名.jpg: "data:image/jpeg;base64,…"}`** —— 图片走 HTTP 回传,
    **MinerU 容器不必与 server 共享文件卷**,server 自己落盘(简化了 M1.5)。
    另有 `POST /tasks` + `GET /tasks/{id}/result` 异步模式与 `GET /health`。
  - 好处:MinerU 那 4.9GB 依赖树永不进 server 镜像。
- **解析产物**(实测,CLI 模式 `<output_dir>/<文件名>/auto/`):
  ```
  ├─ <名>.md                     # 主产物,图片写作 images/<sha256>.jpg 相对路径
  ├─ images/                     # sha256 命名的 jpg(图/表/公式各自截图)
  ├─ <名>_content_list.json      # ★ 拍平块序列,带 page_idx + bbox(origin_ref 数据来源)
  ├─ <名>_content_list_v2.json   # 新增:按页分组 + 嵌套 content
  ├─ <名>_middle.json            # 块→行→span,带 page_size(PDF point)
  ├─ <名>_model.json             # 模型原始推理结果
  ├─ <名>_origin.pdf             # 新增:原 PDF 副本
  └─ <名>_layout.pdf / _span.pdf # 布局与阅读顺序可视化(人工查质量,很好用)
  ```
  - content_list 实测 type:`text`(带 `text_level` 表标题层级)、`table`(`table_body` HTML)、
    `image`、**`chart`**(pipeline 下 `content` 恒空)、`equation`(LaTeX)、
    **`aside_text` / `page_number` / `header` / `footer`**(页边噪声,md 里已丢弃,
    自己用 content_list 时必须过滤)。
  - ⚠ **这份 type 清单不可当成封闭枚举**(2026-08-23 踩坑,见 §9):`ContentBlock.type`
    原来写成 Literal,实测公司政策 PDF 吐出 `header`/`footer` 不在枚举里,
    pydantic 直接 ValidationError —— 一个陌生块把整篇文档打成 parse failed。
    现在 `type: str`,语义判断交给 `CONTENT_BLOCK_TYPES` / `NOISE_BLOCK_TYPES` 两个集合,
    集合外的类型按噪声丢掉并计入 `ParseStats.dropped_by_type`。
  - **bbox 坐标系**:content_list 的 bbox 是**每轴各自归一化到 0–1000** 的整数(原点左上,页面尺寸无关);
    middle.json 的 bbox 是 PDF point,配同页 `page_size`。origin_ref 存前者。
- **解析质量实测**(sample-paper-3p):布局/阅读顺序/双栏切分**全对**;正文、标题层级、断词合并**优**;
  Figure 1/2 正确切图并关联 caption;行间公式 LaTeX 正确,行内公式可读性一般;
  表格分档 —— Table 2(小表)**全对**,Table 1(带 rowspan)列错乱且丢 3 行,
  Table 3(COCO 大表)**严重错乱**。→ 正文够用,复杂表格靠第 3 步人工校对兜住,
  **这正说明"解析校对"人工关是必需项**。不需要降级 pymupdf4llm。
- 沙箱落点:`tmp/s1-dev/parse_pdf.py`(封装 HTTP 调用)+ `tmp/s1-dev/docker/`;
  集成落点:`server/app/services/exact_qa/parser.py`。

### M1.5 解析产物的文件存储与图片展示

MinerU 会把 PDF 里的图片解析成独立文件,markdown 里是相对路径引用——**要在网页上显示,必须有文件 storage 与静态服务这一环**,这是隐藏复杂度,单独列出:

- **实测简化**(Step 0):MinerU 走 HTTP 时以 base64 data URI 回传图片,**server 与 MinerU 容器无需共享卷**,
  server 自己把图片写进 `FILE_STORAGE_DIR/parses/{document_id}/images/`,md 里 `images/<sha256>.jpg` 相对路径不变。
- **存储**:解析产物目录原样入 `FILE_STORAGE_DIR/parses/{document_id}/`(S0 已有本地文件存储约定),`documents.meta` 记产物目录相对路径;校对保存为同目录新文件(`reviewed.md`),原始解析件保留可对比。
- **图片出口**:后端加文件服务端点(如 `GET /api/files/parses/{document_id}/images/{name}`,或 FastAPI StaticFiles 挂载),前端才能显示图片。
- **路径改写(Step 1 定稿)**:**由后端改写**——返回校对文本、返回命中答案时,把 md 里的
  `images/<sha256>.jpg` 改写为 `GET /api/files/parses/{document_id}/images/{name}`。
  选后端不选前端渲染器配 baseURL 的理由:答案文本会被多处消费(校对页、审核台、对话消息、
  未来导出),改写集中在一处才不会漏;沙箱侧已固定为 `schemas.py:FILE_SERVICE_URL_FMT` /
  `image_url()`,集成时整体平移。**落库存的一律是相对路径**(`images/xxx.jpg`),
  URL 只在出口临时拼,存储目录搬迁/域名变化都不影响历史数据。
- **校对编辑约束**:右侧编辑器允许删图,但不破坏未删图片的引用路径。
- **注意**:采纳后的正式 QA `answer` 若含图片引用,问答命中返回时同样走文件服务——图片 URL 方案必须一次定对,避免答案里存了会失效的路径。
- 沙箱阶段图片只需存在于 `out/` 目录、md 里保持相对路径即可(CLI 阶段不需要网页显示);本模块的实现全部发生在集成阶段,但**方案在 Step 1 契约时就要定死**。

### M2 QA 候选抽取(LLM)

- 输入:**校对后的** Markdown;输出:候选 QA 列表 JSON。
- ★ Step 0 发现:**MinerU 的 md 里没有任何页边界信息**,而 origin_ref 要 page_idx。
  方案:`parse_pdf.py` 从 content_list 自己拼一份**带页标记的 markdown**
  (过滤 `aside_text`/`page_number`,每页开头插 `<!-- page: N -->`),校对页展示/编辑的就是这一份,
  抽取时 LLM 直接读得到页码(替代"用 quote 反向 fuzzy match 找页码")。✅ Step 1 已定稿(见 §8.3b)。
- 每条候选的结构(即 `staging_items.payload` 的 qa_pair schema + `origin_ref`):
  `{standard_question, answer, keywords, origin_ref:{quote 原文片段, page_idx}}` + `confidence` 置信度。
- 结构化输出(沙箱阶段 openai SDK 的 json_schema 直调,main 模型 gpt-5);长文档分段抽取再合并。
- 质量硬约束在这一层实现:答案为空 / 无原文引用 / quote 在源文本中定位不到的候选直接丢弃,丢弃数记入统计。
- 本 step 的主要工作是**调 prompt**:对着 sample-paper-3p 跑几十轮对比质量,全程不碰前端。
- ★ Step 3 实测结论(38/41 保留):
  - prompt 的三条关键硬规则:**问题必须自包含**(不许 "it / this paper / Table 1")、
    **quote 必须逐字**、**答案不许是指针**("见表 1" 一律不要);再加一条**禁止答案重复**
    (同一事实的多种问法归 M3,否则候选列表里成对冒重复)。
  - 表格事实只在"行列对应明确"时才抽:实测解析错乱的 Table 1/Table 3 **零产出**,
    解析全对的 Table 2 出 3 条逐行候选(quote 就是 `<tr><td>…`,bbox 指向表块)。
  - **quote 定位要带修复**:模型爱把 `AP<sub>50</sub>` / `$x , y$` 这类排版标记改写掉,
    整段匹配就失败。做法是二分取"能对上的最长前缀"(≥40 字符)作为 quote,
    仍对不上才丢(实测 quote_not_found 从 6 降到 1)。
  - 近似重复要用词集 Jaccard(≥0.8)判,不能只查字符串全等。
  - bbox 由我们用 content_list 回填(模型只填 page_idx 作兜底),实测回填率 37/38,
    缺的那条是 quote 跨块——契约允许 bbox 为空。
- 沙箱落点:`tmp/s1-dev/extract_qa.py`;集成落点:`server/app/services/exact_qa/extractor.py`。

### M3 相似问题生成(LLM)

- 输入:一条 QA(标准问+答案);输出:3–5 条改写问法(string[])。
- 用 light 模型(gpt-5-mini),独立于 M2——抽取管"从原文挖出什么",相似问生成管"同一问题有几种问法",目标不同,prompt 分开调、效果分开评。
- 流水线位置:抽取 Job 在 M2 产出候选后对每条调 M3 填充 `similar_questions`;审核台上人可增删改。
- ★ Step 4 实测结论(36 条 → 144 句改写):
  - 两道代码硬约束:**与标准问相同的改写直接丢**(每轮稳定 16 条,留着白占一行向量);
    **跨条冲突检测**——一句改写与别的候选的问题面 Jaccard ≥0.75 就丢
    (同一句问法映射两个答案 = 检索必错;同样带"区分性 token 必须一致"的保险)。
  - ⚠ prompt 的关键一条是**不许把问题问宽**:v1 给"用了哪些训练技巧"生成了
    `How is YOLOv3 trained?`,直接导致 M4 里"训练要多久/学习率策略"这类**原文没答案**的问题
    以 0.70+ 命中它。加反例后消失。
  - 但标准问本身的宽度是 M2 的产物,M3 改不动 → 必须由 M4 的复核关兜住。
- 沙箱落点:`tmp/s1-dev/gen_similar.py`;集成落点:`server/app/services/exact_qa/similar_gen.py`。

### M4 向量检索(Embedding + 阈值)

- **索引面**:标准问 + 每条相似问各自 embedding(text-embedding-3-small,dim 由 `EMBEDDING_DIM` 配置)。
- **检索**:用户问题 embedding → 余弦相似度 top-k → 按阈值分档(如 ≥0.90 直接命中返回原答案;低于下限未命中)。阈值可配置,本 step 用真实问题调出来。
- 沙箱阶段用 **numpy 内存索引**验证效果与阈值;集成阶段替换为 `exact_qa_vectors`(pgvector,一问一行,item 问题集合变化时全删重建——DB-DESIGN 已定)。
- ★ Step 5 实测结论(27 条人写评测集:15 真实问法 / 7 越界 / 5 **同领域但原文无答案**的困难负例):
  - 分数分布:正例 0.613–0.912、越界负例 0.129–0.384、**困难负例 0.613–0.827**。
    → 阈值只切得开"越界",切不开"同领域没答案"。定稿 `hit=0.55` / `borderline=0.40`
    (0.40–0.60 区间内正例/越界表现完全相同,取 0.55 给召回留余量)。
  - **精度不能靠抬阈值买**:抬到 0.75 只挡掉 3/5 困难负例,正例从 14 掉到 8。改用两道正交的关:
    ① **区分性 token 护栏**(纯代码,复用 M2/M3 那道保险):查询里的含数字 token(型号/分辨率)
       命中面里没有 → 降级。实测拦下 2 条零误伤,含最危险的
       「416×416 的 mAP」以 **0.827** 命中「320×320」那条。
    ② **light 模型命中复核**(`--gate`,只在即将命中时调一次 gpt-5-mini,存疑即判否):
       挡下另外 3 条纯语义邻近的困难负例。
  - 三种配置:纯阈值 21/27 → +护栏 23/27 → **+复核 26/27**(正例零误杀;命中时 +2.9s)。
  - 唯一未通过的一条是 **recall 缺口不是错答案**:短问法 "how are the box priors chosen?"
    没命中那条**复合问题**候选(既问方法又问数量),落 BORDERLINE 回生成。
    处置交给采纳关的人(审核台可改问题文本,把复合问拆开)。
- 沙箱落点:`tmp/s1-dev/retrieve_qa.py`(`--q --verbose` / `--eval` / `--sweep`)
  + 评测集 `eval_questions.json`;集成落点:`server/app/services/exact_qa/indexer.py` / `retriever.py`。

### M5 问答链路接入(仅集成阶段)

- 在 S0 已定型的 `run_chat()` 骨架里插入 `retrieve_exact_qa` 阶段:命中 → 原样返回 `answer`(零改写、不调生成模型),消息标注 "Verified Answer",写 `message_citations`(citation_type='exact_qa');未命中 → 落回 S0 的直接生成。
- ★ 命中判定用 M4 定稿的三段式:阈值 → 区分性 token 护栏 → light 模型复核(Step 5 实测,
  缺任何一道都会把"同领域但原文没答案"的问题错标成 Verified Answer)。
  BORDERLINE 也走生成,但必须 `@traced` 记分数/命中面/复核否决理由——这是后续调阈值的唯一依据。
- 全阶段走 S0 的 `@traced` 埋点,SSE 事件协议只加事件类型不改协议。
- 无沙箱落点(检索逻辑已由 M4 验证);集成落点:`services/chat/` 现有链路 + 复用 M4 的 retriever。

---

## 6. 外部服务与依赖包

| 依赖 | 用途 | 引入方式 | 风险/备注 |
|---|---|---|---|
| **MinerU 3.4.5**(pipeline 模式) | PDF → md + images + content_list.json | **Docker 自建镜像**(`docker/mineru/`,装 `mineru[pipeline]`+`six`),常驻 `mineru-api` 服务,后端 HTTP 调用;永不进 server 依赖树 | ✅ Step 0 已实测通过:权重 1.0GB、峰值内存 2.4GB、CPU 约 6s/页;正文质量优、复杂表格需人工校对。不需要兜底 pymupdf4llm |
| OpenAI gpt-5 | QA 抽取(结构化输出) | 沙箱:openai SDK 直调;集成:S0 Provider 层 | prompt 质量是 M2 核心工作量 |
| OpenAI gpt-5-mini | 相似问题生成 | 同上 | |
| text-embedding-3-small | 问题向量化(1536 维) | 同上 | |
| numpy | 沙箱内存检索 | s1-dev 内 `uv add` | 集成后不需要 |
| pgvector | 正式向量检索 | S0 已就位 | 仅集成阶段 |
| react-pdf(pdf.js) | 校对页左侧 PDF 预览 | `web/`,前端阶段引入 | |
| Markdown 编辑器 | 校对页右侧可编辑文本 | 先受控 textarea + 预览,够用再升级 | 校对以删和改为主,不求富文本 |
| **playwright-mcp** | 前端 stage 的自测手段(真浏览器点一遍,见 §7.1) | 已在 MCP 里连好,`npx @playwright/mcp` | 只在开发期用,不进项目依赖树 |

沙箱包进 `tmp/s1-dev/pyproject.toml`(独立 `uv add`);集成时正式依赖再进 `server/`(`uv add`)与 `web/package.json`。

---

## 7. 开发步骤:后端驱动前端,沙箱驱动集成 ★

原则(与 PRD §9.4 六步一致):**先让每个核心模块在 tmp 沙箱的命令行里单独跑通、调到效果满意,再集成完整后端,最后写前端**。AI 效果问题和界面工程问题分开验证,互不拖累。

```
━━━━━━━ 阶段一:tmp/s1-dev/ 沙箱(不碰正式代码库)━━━━━━━

Step 0  ✅ 已完成 —— MinerU 本地部署验证(Docker)★
        为什么排最前:MinerU 的输出格式(md 结构、图片相对路径、content_list 的
        page_idx/bbox)直接决定 origin_ref 契约、文件存储方案、校对页数据形态——
        没亲眼看到真实产物就定契约,大概率返工。
        做的事:独立环境装 mineru[all] → 下载模型 → pipeline 模式解析
        tmp/sample-paper-3p.pdf → 逐个检查产物,记录:
        ① 安装/模型下载耗时与坑  ② 3 页 PDF 在本机(MPS/CPU)的解析耗时
        ③ md 质量:Figure 1/2 是否切出图、Table 1–3 还原成什么(HTML/md 表)、
          公式还原效果、标题层级  ④ content_list.json 实际结构  ⑤ 图片命名与体积
        产出:MinerU 实测记录(结论已抄进本文 §5 M1,原始记录随沙箱删除)
        结论:Docker 自建镜像 + 常驻 mineru-api 可用;质量与速度均可接受,不降级 pymupdf4llm。
        对本计划的修订已回写进 §5 M1 / §5 M1.5 / §6 / §8。
        ▼
Step 1  ✅ 已完成 —— 定数据契约(基于 Step 0 实测格式)
        产出 tmp/s1-dev/pyproject.toml(独立 uv 项目)+ schemas.py + check_contract.py:
        · 产物文件命名与图片 URL 方案常量化(各脚本不许自己拍路径)
        · MinerU 侧:ContentBlock(实测 7 种 type)/ PageInfo / ParseResult / ParseStats
        · 候选侧:OriginRef / QaCandidate / DropReason / ExtractStats / QaCandidateSet
        · M3/M4:SimilarQuestions / HitTier / RetrievalCandidate / RetrievalResult
        验收:`uv run python check_contract.py` 用 Step 0 真实产物跑通——49 块全部通过
        ContentBlock 校验、噪声过滤 2 块、page_size 612×792、bbox 归一化换算对上、
        图片 URL 改写与 quote 定位校验通过。
        §8 各契约点结论已回写(见下),M1.5 图片方案已在 §5 定稿。
        (沙箱契约将在集成时平移为 server/app/schemas/exact_qa.py → make types)
        ▼
Step 2  ✅ 已完成 —— M1 解析脚本 parse_pdf.py(HTTP 调常驻 mineru-api + 产物落盘)
        `uv run python parse_pdf.py --pdf ../sample-paper-3p.pdf [--force]`
        产出 out/parse/{document_id}/:paged.md(带页标记,校对与抽取的统一载体)/
        parse_result.json(pages 页尺寸 + 已过滤噪声的块序列 + stats)/ images/*.jpg /
        mineru_raw.md(MinerU 原始 md,只作校对对照,不进下游)。
        实测:3 页 22.1s、47 块(丢噪声 2)、表 3 图 2 公式 1、图片 6 张 276KB。
        ⚠ 实测坑:`/file_parse` 的 content_list / middle_json 是 **JSON 字符串**(CLI 落盘是对象),
        必须 json.loads 一次(`_as_json()` 已统一);已回写 notes。
        CLI 形态的可视化产物(_layout.pdf 等)改落 out/parse-cli/,避免被 --force 清掉。
        ▼
Step 3  ✅ 已完成 —— M2 抽取脚本 extract_qa.py(gpt-5 结构化输出,prompt 已调两轮)
        `uv run python extract_qa.py --document-id sample-paper-3p --max-chars 9000`
        实测(v3 定稿,三轮):paged.md 14943 字符 → 2 段 → 原始 39 条 → **保留 36 条**
        (丢弃 quote_not_found 3、duplicate 0),bbox 回填 36/36,耗时 263s。
        质量:问题与答案自包含、数字与论文真值一致、页码正确;逐字 quote 校验拦下过一条
        **把公式里 σ(t_x) 抄成 c(t_x)** 的候选(说明它能拦事实性错抄,不只防格式漂移)。
        ⚠ 判重踩过一个坑:只看词集 Jaccard 会把「ResNet-152 的指标」当成「ResNet-101 的指标」
        的重复而**静默丢知识**,已加「区分性 token(含数字的词)必须一致」这道保险。
        ⚠ 表格来源的候选有风险:Table 3 行标签错位,模型靠上下文猜对了数字,
        引用与 bbox 却都"对得上"——采纳关必须对着原图核表格类候选。
        详见本文 §5 M2 的实测结论(沙箱笔记已随沙箱删除)。
        本轮输入是 paged.md:reviewed.md 是第 3 步人工关的产物,留到 Step 7 由真人产出,
        脚本已实现"有 reviewed.md 用它、没有则退回 paged.md 并打提示"的契约。
        ▼
Step 4  ✅ 已完成 —— M3 相似问脚本 gen_similar.py(gpt-5-mini,8 路并发,36 条约 50s)
        `uv run python gen_similar.py --document-id sample-paper-3p`
        实测(v2 定稿):原始 160 → 保留 **144 句改写**(平均 4.0 条/QA),
        丢弃"与标准问相同"16、跨条冲突 0;索引面合计 **180 句**(标准问 36 + 改写 144)。
        ⚠ prompt 的关键一条由 M4 评测倒逼加出来:**不许把问题问宽**
        (`How is YOLOv3 trained?` 这种改写会把原文没答案的问题吸过来)。
        ▼
Step 5  ✅ 已完成 —— M4 检索脚本 retrieve_qa.py(numpy 内存索引 + 27 条人写评测集)
        `uv run python retrieve_qa.py --sweep` / `--eval --gate` / `--q "..." --verbose`
        阈值定稿 **hit=0.55 / borderline=0.40**;单查询 0.39s;embedding 本地缓存不重复付钱。
        ★ 核心结论:阈值只切得开"越界问题"(0.13–0.38),切不开"同领域但原文没答案"
        (0.61–0.83,与正例完全重叠)。补两道与阈值正交的关——**区分性 token 护栏**(纯代码)
        + **light 模型命中复核**(只在即将命中时调一次)。
        三种配置:纯阈值 21/27 → +护栏 23/27 → **+复核 26/27**(正例零误杀)。
        详见本文 §5 M3/M4 的实测结论。

━━━ 集成门槛(gate):✅ 全链路 CLI 已走通(parse → paged.md → extract → similar → retrieve),
    各模块质量满意 → 可进阶段二。唯一留给人工关的已知项:复合问题拆分、表格来源候选对原图核。━━━

━━━━━━━ 阶段二:集成进正式代码库 ━━━━━━━

Step 6  ✅ 已完成 —— 后端集成(每个子步骤的自测全绿):

  6a  契约与骨架
      · sandbox schemas.py → server/app/schemas/exact_qa.py;新建
        server/app/services/exact_qa/(同步建 claude.md + architect.md)
      · config + .env.example 补三项:EXACT_QA_HIT_THRESHOLD=0.55 /
        EXACT_QA_BORDERLINE_THRESHOLD=0.40 / EXACT_QA_HIT_GATE=true
      自测 ✅:make lint / make test(32 passed)/ 把 .env 临时改成异值(hit=0.61 gate=false)
      再读 settings —— 确认走的是文件不是默认值。另补了 MINERU_API_URL / MINERU_TIMEOUT_SEC。

  6b  纯函数平移 + 离线单测
      · extract / similar / retrieve 的纯逻辑(判重、区分性 token 护栏、命中分档)
        平移进 services/exact_qa/,openai 直调换 S0 Provider 层(main/light tier)
      自测:新增 server/tests/test_exact_qa_*.py —— 沙箱 27 条评测集里**不依赖 embedding**
      的部分做成 fixture(护栏该拦的两条、分档边界、判重的 ResNet-101/152 那个坑)。
      ★ 这是 S1 唯一必须写单测的地方:这几个函数有确定的输入输出,且**改错了不报错、
      只是静默给错答案**——沙箱里踩过两次,不能靠肉眼守。
      联网部分用 `server/scripts/smoke_exact_qa.py`(照 smoke_llm 套路)真调一次 LLM 验通路。
      自测 ✅:47 条新单测(matching 13 / retriever 11 / extractor 17 / similar 6),
      离线共 79 passed;冒烟三个 LLM 调用点全通(抽取 8/8 带 quote+bbox、相似问 34→31、
      复核正例放行负例否决,$0.032)。
      ⚠ 平移时真踩到的:Provider 只有 `complete(json_schema=)`,沙箱用的是
      `responses.parse(text_format=)` —— 差的一层补在 `services/exact_qa/llm.py`,三处共用。

  6c  存储层 + pgvector
      · 采纳事务(staging → exact_qa_items + exact_qa_vectors 一问一行)、状态流转
      自测:`make db-reset && make migrate && make seed` 后跑
      `server/scripts/smoke_exact_qa_store.py` —— 灌沙箱产物 → 采纳 → 查回 top-k,
      ★ 关键断言:**同一 query 的 pgvector 分数与沙箱 numpy 分数差 <1e-3**。
      这是"内存索引换 pgvector"唯一真正会出错的地方(距离算子选错/没归一化),必须对数。
      自测 ✅:8 条 QA / 40 个索引面,**分数最大偏差 2.85e-07**(算子=cosine,阈值可原样沿用);
      分档实跑 0.647 hit / 0.112 miss / 0.535 borderline(护栏报出缺 `19`);下线后向量行 5→0。
      ⚠ 第一版对数写错并被自己的断言抓住:拿"重新 embed 的向量"跟库里分数比,差 2.3e-3。
      根因是 **OpenAI embedding 跨批次不确定**(同句不同 batch 余弦 0.99942,逐维差 3e-3),
      改成读回库里存的那份向量才是在考算子。副产品结论:**阈值只在 ±0.005 尺度上有意义**。

  6d  两个 Job + REST API + 文件服务端点
      · qa_parse / qa_extract 两个 Job,由用户确认动作衔接;上传、文档列表、校对文本
        读写、确认抽取、候选列表、采纳/不采纳、正式 QA 管理;解析产物图片出口
      自测:`make api` 起服务,把整条链路固化成 `server/scripts/smoke_s1_api.sh`
      (上传 → 轮询解析完 → 读校对文本 → 写回 → 确认抽取 → 列候选 → 采纳一条 → 列正式 QA),
      可重复跑、断言 HTTP 码与关键字段,**不靠手打 curl**;图片端点 `curl -I` 验 200 + content-type。
      此时前端还一行没写。
      自测 ✅:13 步全绿。解析 18s(3 页 47 块 6 图)→ 校对文本带页标记且图片 URL 全改写
      → 写回 reviewed.md → 抽取 17 条候选 / 68 句改写 → 采纳 1 条(5 个索引面)/ 不采纳 1 条
      → 漏斗 {17,15,1,1} stage=review_qa。**反例也断言**:非 PDF 409、路径穿越 404、
      重复确认抽取 409、重复采纳 409、不采纳空理由 422。

  6e  M5 接入 run_chat + trace
      自测:冒烟脚本对 /api/chat 打三个问题——正例 / 越界 / **困难负例**,断言:正例带
      "Verified Answer" 标注与 message_citations,另两个不带且落回生成;BORDERLINE 的
      trace 能查到分数 + 命中面 + 复核否决理由(§5 M5 要求的埋点,不埋后面没法调阈值)。
      自测 ✅(`scripts/smoke_s1_chat.py`):正例(用扰动过的相似问问)0.864 命中、答案与库里
      **逐字相同**、`stages=['retrieve_exact_qa']` —— **没有 generate stage**,这就是"零改写"的
      机器可证明形式;越界 0.112 miss、困难负例 0.403 borderline 且 `guard_missing=['19']` 可查;
      SSE 实打一次:`meta → stage_start → stage_end → verified → token → done`,命中时无
      generate 的 stage_start。协议只增不改(新增 `verified` 事件 + `done.verified`)。
      ⚠ 环境坑:8000 上曾同时有两个 uvicorn(上一场 make dev 遗留的 --reload),
      SSE 那步落哪个不确定 = 抛硬币;清成一个再重跑才算数。
        ▼
Step 7  ✅ 已完成 —— 前端(每个页面做完立刻用 playwright-mcp 在真浏览器里点过;
        四个 stage 共抓到 4 个真 bug,都是当场修完重跑该 stage):

  7a  ✅ 候选 QA 审核台 —— 不是复制一份审核台,而是给泛型审核台加了**动作层**
      (`ReviewActions`:approveLabel / requireRejectNote / defaultStatusFilter / publish / bulk
      + approve / reject),本域登记 `qaPairActions` 实现"采纳即发布"。审核台本体的流程一行没改。
      自测 ✅:采纳一条 → pending 15→14、该条从列表消失、正式库 9→10 且新条 5 个索引面;
      不采纳第一次点只展开理由框且按钮置灰,填了才提交(理由入 `review_note`);
      下线 → 5 faces→0 faces + disabled,库里向量行 5→0(正式行留着)。
      ⚠ 抓到:按 `status === 'active'` 判断,而枚举是 `enabled/disabled` —— Disable 按钮永远不渲染。
      顺手修掉 S0 遗留的 favicon 404,让"控制台无 error"这条自测标准真的可用。

  7b  ✅ 解析校对页 —— 左边原件 PDF(浏览器原生阅读器 + `#page=N`,不引 pdf.js;
      为此后端加了 `GET /api/files/documents/{id}/pdf`),右边解析 markdown 的 Edit / Preview
      (react-markdown + remark-gfm + **rehype-raw**:MinerU 的表格与上下标是原始 HTML,
      不允许 HTML 就没法校对)。
      自测 ✅:两张图 naturalWidth 698/657(真出图不是 404 占位);编辑 → Save → reviewed.md
      字节数变化、刷新后改动还在;带 `?page=2&quote=…` 进来自动选中那句原文并滚过去、
      PDF 落在 `#page=2`;重复确认抽取 409 + toast,没造出第二个 Job。
      ⚠ 抓到两个:① 域页 import AppLayout 形成 ESM 环 → 运行时
      `Cannot access 'DOMAINS' before initialization`;把右侧面板 context 拆到
      `layouts/rightPanel.tsx` 断环(纪律已回写 DOMAIN-DEV-GUIDE)。
      ② 自动定位引用时好时坏 —— 文档与文本是两个请求,effect 触发时编辑器还没挂上;改挂 ref 回调。
      **与原计划的有意偏差**:bbox 高亮没做 —— 原生 PDF 阅读器上得叠画布才画得出框,
      代价与收益不成比例;改成"跳到对应页 + 在编辑器里选中逐字引用"。bbox 仍在原文对照面板
      里以数字显示(数据没丢),要真画框就得引 pdf.js,留作可选项。

  7c  ✅ 上传入口 + 文档列表(stage / 漏斗计数 / 一行一个动作)。
      自测 ✅:真上传 → 立刻出现 `Queued` 行 → **没刷新页面**自己走到 `Ready to proofread`
      (3p · 47 blocks),动作按钮跟着从 Proofread 变 Review candidates;
      到终态后 4 秒内 `/documents` 新请求数 **0**(轮询真的停了);
      传非 PDF → 409 + toast,库里 documents 数不变(没留孤儿行)。
      `apiUpload` 刻意不设 Content-Type(multipart 的 boundary 必须浏览器生成)。

  7d  ✅ 对话页 Verified Answer 标注 + 引用可展开。
      自测 ✅:正例带徽标 + 答案与库里逐字相同 + 引用显示命中面 / 0.864 / p1,展开是
      `SIMILAR QUESTION · PAGE 1` + 原文摘录;**trace 面板 1 stage —— 没有 generate**;
      越界问题无徽标无引用,trace 是 retrieve_exact_qa(miss) + generate。控制台 0 error。
      ⚠ 抓到:引用行按钮嵌在助手气泡的 `<button>` 里 = 非法 HTML(React 直接报错),
      气泡改成 `role="button"` 的 div(带 Enter/Space 键盘支持)。
      ★ 一个值得记的观察(不是 bug):另一条正例检索到 **0.9244** 却被 light 复核否决,理由
      `oversimplified/incorrect (omits loss form, parameterization and scaling)` ——
      **复核关会因为"答案对但过于简略"挡下合法命中**,阈值调不动它。Step 8 用真实业务文档时
      要重新判断:收紧 gate 的 prompt,还是接受这种保守(演示里"宁可不标 Verified"未必是坏事)。

      **已知缺口(Step 8 的边缘)**:历史消息读回来时 Verified 标注消失 ——
      `MessageOut` 没有 citations 字段,标注只存在于流式那次的事件里。
      要修 = 后端加一个字段 + `make types` + useChat 映射一次。
        ▼
Step 8  ✅ 已完成 —— 端到端 + 回归 + 边缘:

  8a  ✅ 换虚构业务手册走全程。**PRD §2.0 说演示公司与数据全为虚构**,
      所以"真实业务文档"= 按 PRD 的产品线(HC 储能柜 / INV 逆变器 / EMS)自己写一份形态真实的
      4 页英文手册:质保期与容量保持率、延保定价、免责条款、渠道折扣档、分州交付周期、
      认证与合规、对外可用话术 —— 正是精准 QA 该管的"答错就是错误承诺"那类内容。
      源文件 `company-handbook.html` → headless Chrome 打印成 `company-handbook.pdf`
      (4 页 / 7 表 / 142 KB)。清理沙箱时这两个文件搬进 `server/scripts/fixtures/`(手动演示的上传素材);
      演示数据要不要预置进库归 S5(§9.2 的演示包装)决定。
      实跑:解析 12s(4p 41 块 7 表)→ 校对修掉 **7 处 MinerU 瑕疵** → 抽取 **23 条候选**
      → 采纳 8 条(1 条单条 + 7 条走新加的批量)→ 对话命中 0.780 原样返回标准答案。
      ★ 校对关的价值当场可见:MinerU 把"−20 °C to +50 °C"识别成一串 LaTeX
      (`$- 2 0 ~ ^ { \circ } \mathsf { C }$`),不修的话抽出来的那条 QA 就是乱码;
      修完抽取产出的是干净的"Operation outside the specified ambient range of -20 °C to +50 °C"。
      ★ 最强的一条演示点:**同一份文档里没被采纳的事实,问它不带标注**
      ("取消费 15%" 候选在册但没采纳 → 无徽标、2 个 stage、模型如实说不知道)。

  8b  ✅ 回归。`make lint` / `make test`(79 passed)/ `make smoke-s1`(四个脚本)
      / `make smoke-sse` / `make demo` 全绿;Step 7 的浏览器旅程用 playwright 重走了一遍
      (上传 → 校对 → 抽取 → 审核 → 对话 → 删除),每页收尾看控制台,0 error。
      ⚠ **回归抓到一个真问题**:`smoke_s1_chat` 的正例红了 —— 检索到 0.8866,却被 light
      复核否决,理由 `Gives ambiguous/uncertain GPUs rather than a definitive statement`。
      这是 Step 7d 记的那个现象第二次出现(上次理由是"过于简略"),这次把回归脚本打红了。
      **结论:不是阈值问题,是 gate 的 prompt 取向错了** —— 复核关该判"答的是不是这个问题",
      不该给答案的完整度/确定性打分(内容是人已经审过的,原文自己就含糊)。
      改法:GATE_PROMPT 明确列出**不构成否决的理由**(简短、含糊、少了没问的细节、风格朴素),
      否决只留给"答的是另一个对象/另一个方面"。并把两次误否决固化成
      `smoke_exact_qa.py` 第 ④ 步的用例表(2 条误否决 + 2 条邻近实体),以后再动 prompt 能量出来。
      实测:4 条全对,而且 ③ 的 Darknet-19 困难负例这次也被挡下了(以前是护栏兜的)。

  8c  ✅ 补边缘(三件,都做了自测):
      · **历史消息带回标注**(Step 7d 记的已知缺口):`MessageOut` 新增 `citations` + `verified`,
        引用一次查完按 message 分组(不做 N+1);`verified` 的判定规则只写在后端一处
        (有 exact_qa 引用即为真),前端不猜。顺带把引用从裸 dict 改成真 schema
        (`MessageCitationOut` + `CitationExtra`,后者 `extra="allow"` 给 S2/S3 留位),
        前端那份手写的"约定型" `MessageCitation` 就此删掉 —— 契约先行的纪律回到位。
      · **批量采纳**:动作层加 `bulkApprove(items)`(串行,返回成功条数)+ `bulkReject: false`
        (理由必填,批量填一个理由等于没理由)。实跑 4 条 1.5s,每条 5 个索引面都建上了。
      · **删除文档**:`DELETE /api/exact-qa/documents/{id}`,清两个 Job + 文档行 + 上传原件 +
        解析产物目录;**有已发布问答的 409**(正式 QA 的出处在候选行的 origin_ref 里,
        删了就悬空)。界面是两步确认。正反例都进了 `smoke_s1_api.sh`(第 14/15 步)。
      · 回归里另抓到两处**脚本自己的**问题(不是产品):`store` 冒烟下线那步没过滤
        `status='enabled'`(库里有下线过的条目就会误判);新写的第 15 步 break 条件漏了
        `published`(qa_parse 的终态,见 DB-DESIGN 那两点收窄),白等满 180s。都修了并复验。
      · 失败重跑**没有新增**:解析失败的入口已经在校对页右侧的 JobProgress(S0 的"从失败步骤重跑"),
        抽取失败在文档列表那一行是 `Retry extraction` —— 都在,不重复造。
```

### 7.1 自测纪律 ★

**每个 stage(含 Step 6 的 6a–6e、Step 7 的 7a–7d)做完立刻自测,通过才进下一个 stage。**
不允许攒到最后一起测——集成期的 bug 一旦叠起来,分不清是平移错了还是接线错了。
自测挂了就当场修,修完**重跑该 stage 的全部自测**,不许"下个 stage 顺带修"。

手段按代价从低到高,能用低的就不用高的:

| 层 | 手段 | 用在哪 |
|---|---|---|
| 1 | `make lint`(ruff + eslint + tsc)、`make test`(离线 pytest) | 每个 stage 无条件先跑,零成本 |
| 2 | 冒烟脚本 / curl(`server/scripts/smoke_*`) | 后端 stage;**固化成脚本**,回归时能重跑 |
| 3 | **playwright-mcp 真浏览器** | 前端 stage,凡是"点了才知道对不对"的一律用 |

**playwright-mcp 用法约定**(Step 7 / 8):

1. 先 `make dev` 起真前后端(前端 5173,`/api` 代理到 8000),**不用 mock**——
   前端 stage 的自测目的就是验前后端接线,mock 掉就白测了。
2. `browser_navigate` → `browser_snapshot` 读可访问性树定位元素(优先用它而不是截图,
   snapshot 有 ref 可直接点,截图只能看)→ 点击/填写 → 再 snapshot 断言状态变了。
3. **每个页面自测收尾必看 `browser_console_messages`,不允许有 error**;
   前端最常见的失败是接口 404 / 字段名不对,页面看着正常但控制台在报错。
4. 失败时截图存本地临时目录,连同结论写进当轮的自测结论(临时产物不入库)。
4b. 实际用上的工具(Step 7/8 补记):`browser_file_upload`(真传文件)、
   `browser_network_requests`(验"轮询到底停了没")、`browser_evaluate`
   (查 `img.naturalWidth`、数向量行之外的 DOM 事实、等异步状态)。
   ⚠ **`browser_type` 是 fill 语义 —— 会把整个输入框替换掉**。Step 8 就这么把校对页
   一万多字的解析文本冲成了 16 个字符(没保存,刷新即恢复)。要改其中一段:
   先 `setSelectionRange` 选中,再走 `insertText`(真 input 事件,React 收得到)。
5. ⚠ 若当前会话里 playwright 工具不可用(MCP 连上了但工具没加载),重启会话再用;
   不要退化成"我看代码觉得没问题"就算测过。

**自测记录**:开发期间每个 stage 的自测命令 + 结果记一行进一份流水表
(stage / 测了什么 / 通过或失败 / 失败原因与修法),阶段收尾后把有价值的结论收进本文、
流水表本身删掉(它是过程性文档)。这不是形式主义——
沙箱阶段的两个真 bug(把问题问宽、护栏漏掉高分负例)都是**测出来的,不是看出来的**,
不留记录下次会重复踩。

**边界**:S1 只做冒烟级自测,不铺后端单测全覆盖、不做前端组件测试
(面试演示项目,时间花在链路和效果上)。唯一例外是 6b 的纯函数(见上,必须有离线单测)。

每个 Step 独立验收:沙箱阶段的标准是"CLI 输出质量满意",后端集成是"每个子步骤的冒烟脚本全绿",前端是"playwright 在真浏览器里走通且控制台无 error"。

---

## 8. 数据落点与契约待定点(集成阶段用)

现有表直接可用(S0 migration 已建):

| 环节 | 落点 |
|---|---|
| 上传的 PDF | `ingest_sources`(文件存 FILE_STORAGE_DIR) |
| 解析/抽取任务 | `ingest_jobs`(job_type 拆为 `qa_parse` / `qa_extract`) |
| 候选 QA | `staging_items`(item_type='qa_pair',payload 按 DB-DESIGN §8 既有定义,origin_ref 存原文引用,confidence 存置信度) |
| 正式 QA | `exact_qa_items`(source_staging_id 溯源) |
| 向量 | `exact_qa_vectors`(一问一行) |
| 命中引用 | `message_citations`(citation_type='exact_qa') |

**Step 1 定契约需落定、并可能修订 DB-DESIGN 的点**(均以 Step 0 的 MinerU 实测产物为依据):

1. **解析产物与校对文本存哪(Step 1 定稿)**:MinerU 产物目录整体入
   `FILE_STORAGE_DIR/parses/{document_id}/`,`documents.meta` 记 uri;目录内固定四个落点
   (常量在 `schemas.py`):`paged.md`(带页标记的解析文本)/ `reviewed.md`(校对后)/
   `parse_result.json`(页尺寸+块序列+统计)/ `images/`。**不加 `documents.reviewed_uri` 列**
   ——文件名固定,由 document_id 推导即可,少一列少一处不同步。
2. **图片 URL 方案(M1.5,Step 1 定稿)**:端点 `GET /api/files/parses/{document_id}/images/{name}`;
   **改写在后端出口做,入库一律存相对路径**(理由见 §5 M1.5)。
   (Step 0 已确定:MinerU 用 base64 回传图片,server 自己落盘,无需共享卷。)
3. **origin_ref 结构(Step 1 定稿,`schemas.py:OriginRef`)**:
   `{"document_id":"...","page_idx":3,"quote":"原文片段","bbox":[x0,y0,x1,y1]}`。
   - `page_idx` **0 起**(与 MinerU 一致,前端显示时 +1),bbox 用 content_list 的
     **0–1000 每轴归一化**整数坐标(原点左上、页面尺寸无关);前端高亮
     `x_pt = bbox_x/1000 * page_width_pt`,页尺寸取 `parse_result.json` 的 `pages[]`。
   - `bbox` **可空**:quote 跨块时给不出唯一框,此时只用 quote + page_idx 定位。
   - `quote` 逐字摘录,必须能在校对文本里定位到,否则该候选在 M2 直接丢弃
     (计入 `DropReason.QUOTE_NOT_FOUND`)。
   - ⚠ 与 DB-DESIGN §5 现写的示例 `{"source_id","page","quote"}` 不一致(字段名与是否带
     bbox),**归档时按本节改 DB-DESIGN**。
3b. **带页标记 markdown(Step 1 定稿)**:由 parse 层用 content_list 生成 `paged.md`——
   每页开头插 `<!-- page: N -->`(N 从 0 起,常量 `PAGE_MARKER_FMT`),**只保留内容块**
   (常量 `CONTENT_BLOCK_TYPES` = text/table/image/chart/equation),其余一律丢掉 ——
   已知的页边噪声(`NOISE_BLOCK_TYPES` = aside_text/page_number/header/footer/discarded)
   与任何没见过的新类型都走这条路(2026-08-23 修,见 §9)。作为**校对与抽取的统一文本载体**;
   校对页展示/编辑的就是它,M2 优先读 `reviewed.md`,不存在则退回 `paged.md`。
4. **文档状态**:`documents.parse_status` 现有 4 态(pending/parsing/parsed/failed)缺"待校对/抽取中/待采纳"。方案:文档级只管解析态,后续状态由关联 Job 状态推导;或扩展 CHECK 枚举。
5. **Job 状态机语义**:DB-DESIGN 的 `review →(用户点发布)publishing → published` 是"批量发布"语义;我们改为**逐条采纳即发布**,则 qa_extract Job 的 review 态表示"采纳进行中",全部裁决完毕置 published(仅作终态统计,`publish_records` 记漏斗数字)。归档时更新 DB-DESIGN 该节描述。
6. **exact_qa 检索阈值与命中关(Step 5 实测定稿)**:进 config + `.env.example` 三个配置项——
   `EXACT_QA_HIT_THRESHOLD=0.55`、`EXACT_QA_BORDERLINE_THRESHOLD=0.40`、
   `EXACT_QA_HIT_GATE=true`(命中前用 light 模型复核一次)。
   ⚠ 计划早期臆测的 0.90 与实测不符:`text-embedding-3-small` 上真实问法与标准问的余弦
   多在 0.61–0.91,0.90 会把绝大多数正例挡在门外(实测 0.90 只剩 2/14)。

## 9. 上线后踩坑与修复记录

### 9.1 `ContentBlock.type` 用 Literal 收窄 → 一个陌生块打死整篇文档(2026-08-23 修)

**现象**:手动测 `data/company-it-policy.pdf`,文档列表显示 `Parse failed`,错误是
`ValidationError: 1 validation error for ContentBlock / type / Input should be 'text', 'table',
'image', 'chart', 'equation', 'aside_text' or 'page_number' [input_value='header']`。

**根因**:`ContentBlock.type` 写成 `Literal[...]`,枚举取自沙箱阶段那份 arXiv 论文实测到的
7 种类型。真实的公司政策 PDF 有页眉页脚,MinerU 吐出 `header` / `footer` 两种类型不在枚举里,
`ContentBlock.model_validate` 抛异常 —— 而这一步是在 `step_parse` 里对**整个 content_list**
逐块校验,所以一个页眉块 = 整篇文档解析失败。方向错了:content_list 是 **MinerU 的输出**,
不是我们的入参,对它做枚举收窄没有任何收益(不会有人手写 content_list),只有风险
(MinerU 升级、换 backend、换文档类型都可能冒出新类型)。同一个坑当时还留了个证据:
`NOISE_BLOCK_TYPES` 里的 `discarded` 从来就不在那个 Literal 里。

**修法**(`server/app/schemas/exact_qa.py` + `services/exact_qa/{parser,ingest}.py`):

- `type: str`,不再枚举;类型的语义判断改由两个集合表达 ——
  `CONTENT_BLOCK_TYPES`(text/table/image/chart/equation,拼 md 时每种都有分支)与
  `NOISE_BLOCK_TYPES`(aside_text/page_number/**header**/**footer**/discarded)
- `is_noise` 反过来判:**不在内容集合里的一律算噪声** —— 陌生类型自动走丢弃路径,不再抛异常
- 陌生类型不能悄悄丢:新增 `is_unknown_type`,`step_parse` 里 `log.warning`
  (`mineru_unknown_block_types`)并写进该步的 step log;
  `ParseStats` 新增 `dropped_by_type`(如 `{"header": 13, "footer": 5, "page_number": 5}`),
  store 步的 message 一并报出来 —— 只有总数的话,"这篇少了 23 块"分不清是正常页眉还是漏认新类型
- 回归单测 `server/tests/test_exact_qa_parser.py`(5 个用例):页眉页脚页码能过校验且算噪声、
  陌生类型宽容但被标记、内容类型不被丢、拼 md 只渲染内容块、`dropped_by_type` 按类型计数

**实测**(两份公司政策 PDF,MinerU 3.4.5 / backend=pipeline):
`company-it-policy.pdf` 64 块 → 保留 41(丢 header×13 / page_number×5 / footer×5),5 页 6 表 1 图;
`company-travel-policy.pdf` 63 块 → 保留 40(同样的 23 块噪声),2 图。
校对页的 markdown 里不再出现公司抬头(页眉)、"Page 1 of 5"(页码)、
"CLE-IT-POL-011 | Internal use only"(页脚)。全链路复测见 §9.2。

### 9.2 修复后的全链路复测(playwright,2026-08-23)

清库(`make db-reset`)+ 清 `storage/` 后从零走一遍:上传 `company-it-policy.pdf` → 解析
(11.3s,41 块)→ 校对页对照 PDF 检查 5 页文本 → Confirm & extract(74s,55 raw → 28 kept)→
similar(122 → 111)→ 审核台 Accept & publish → Chat 问 "How must Restricted data be stored?"
→ 气泡带 **Verified Answer** + 引用 `[1] 相似度 1.000 p5`,执行轨迹**只有 `retrieve_exact_qa`
一个阶段**(无 `generate`,证明零改写)。控制台 0 error。
