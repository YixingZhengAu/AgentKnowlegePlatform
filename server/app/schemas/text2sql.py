"""智能问数(S3)的出入参契约。前端类型由 openapi 生成,所以这里的字段名就是契约。

三条贯穿本文件的纪律:

1. **口令只在入参里出现一次**(`DatasourceConnIn.password`)。落库是 Fernet 密文,
   出参永远只有 host/port/user/database —— 没有任何接口会把连接串明文还回去。
2. **参数区(`IntentParams`)显式写出三段的已知字段,但每段都 `extra="allow"`**。
   字段级定义的唯一出处是 DB-DESIGN §4.8;这里写出来是为了让前端有类型可用,
   不是为了封死结构(和 `CitationExtra` 同一个理由)。
3. **候选意图的列表与编辑不在这里** —— 走 S0 的泛型审核接口(`GET /api/staging`)。
   本文件只描述 S3 私有的那些动作。
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel

# ============================================================ 数据源


class DatasourceConnIn(BaseModel):
    """连接要素。**这是全项目唯一接收数据库口令的地方**,它只会被加密后落库。"""

    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=3306, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=64)
    user: str = Field(min_length=1, max_length=64)
    password: str = Field(default="", max_length=255)


class DatasourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    conn: DatasourceConnIn
    # 不传就落到唯一的 text2sql 知识库(演示环境只有一个)
    kb_id: uuid.UUID | None = None
    # 只放开 mysql:S3 只实测过这一条方言,没实测过的不该假装支持(见 bizdb.DIALECT)
    db_type: Literal["mysql"] = "mysql"
    #: 运维确认该账号只读。false 时同步与执行都拒 —— 这不是提示,是拒
    readonly_confirmed: bool = False


class DatasourceUpdate(BaseModel):
    """全字段可选:只改名、只换口令、只翻开关都是合法请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    conn: DatasourceConnIn | None = None
    readonly_confirmed: bool | None = None
    status: Literal["active", "disabled"] | None = None


class DatasourceOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    name: str
    db_type: str
    status: str
    readonly_confirmed: bool
    # 从密文解出来的连接要素,**永远不含 password**
    host: str
    port: int
    database: str
    user: str
    last_synced_at: datetime | None = None
    # 治理进度(前端 D1 的"同步状态"要它,数一次比让前端拉全量 schema 再数便宜)
    tables: int = 0
    enabled_tables: int = 0
    described_tables: int = 0
    published_intents: int = 0
    created_at: datetime
    updated_at: datetime


class TestConnectionResult(BaseModel):
    """Test connection 的结果。失败也是 200 —— 连不上是**业务结果**,不是接口错误。"""

    ok: bool
    #: `mysql://user@host:port/db`,不含口令
    target: str
    server_version: str | None = None
    table_count: int | None = None
    error: str | None = None


class JobStarted(BaseModel):
    """派发了一个后台 Job。进度轮询走 `GET /api/jobs/{id}`(S0 的通用接口)。"""

    job_id: uuid.UUID
    job_type: str


# ============================================================ Schema 治理


class EnumValueOut(BaseModel):
    """枚举字典的一项。改写阶段真正需要的是"值 → 含义",裸 string 给不了这个。"""

    value: str
    meaning: str | None = None


class ColumnMetaOut(ORMModel):
    id: uuid.UUID
    column_name: str
    ordinal: int | None = None
    data_type: str | None = None
    is_nullable: bool
    key_flag: str | None = None
    #: 库里原本的列注释:治理素材,不是成品
    physical_comment: str | None = None
    display_name: str | None = None
    description: str | None = None
    is_sensitive: bool
    distinct_count: int | None = None
    is_enum_like: bool
    enum_values: list[EnumValueOut] | None = None
    sample_values: list[str] | None = None
    enabled: bool


class TableMetaOut(ORMModel):
    id: uuid.UUID
    datasource_id: uuid.UUID
    schema_name: str
    table_name: str
    display_name: str | None = None
    description: str | None = None
    physical_comment: str | None = None
    enabled: bool
    row_count_estimate: int | None = None
    column_count: int = 0
    described_columns: int = 0


class TableDetailOut(TableMetaOut):
    columns: list[ColumnMetaOut] = []


class RelationOut(ORMModel):
    """join 提示。`source` 必须能一眼分开真 FK 与命名启发式猜的 —— 可信度不同。"""

    id: uuid.UUID
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str | None = None
    source: str
    description: str | None = None


class SchemaOut(BaseModel):
    """Schema 治理页一次拿全:数据源 + 表(含列)+ join。"""

    datasource: DatasourceOut
    tables: list[TableDetailOut]
    relations: list[RelationOut]


class ColumnPatch(BaseModel):
    """按表保存时的一列。只有出现在请求里的字段会被写。"""

    id: uuid.UUID
    display_name: str | None = None
    description: str | None = None
    is_sensitive: bool | None = None
    enabled: bool | None = None


class TableSave(BaseModel):
    """按表保存(D2 的 Save 按钮):表级字段 + 若干列,一个事务。"""

    display_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    columns: list[ColumnPatch] = []


class DescribeRequest(BaseModel):
    """批量写描述。`fill` 只填空缺(人写的注释逐字保留),`rewrite` 全量重写。"""

    mode: Literal["fill", "rewrite"] = "fill"
    #: 不传就是所有启用的表
    tables: list[str] | None = None


class ColumnSuggestion(BaseModel):
    column_name: str
    display_name: str = ""
    description: str = ""
    enum_values: list[EnumValueOut] | None = None


class DescribeSuggestion(BaseModel):
    """单点 AI 生成的**建议**,没有落库 —— 人在页面上确认后才走保存接口。"""

    table_name: str
    description: str = ""
    columns: list[ColumnSuggestion] = []


# ============================================================ 意图


class ParamFilter(BaseModel):
    """WHERE 的一个可改值参数。运行时只能改 `default_value` 或禁用它。"""

    model_config = ConfigDict(extra="allow")

    param_id: str
    source: str
    operator: str
    value_type: str
    value_shape: str
    default_value: object = None
    predicate_sql: str = ""
    business_name: str = ""
    #: 给改写模型看的**取值说明书**(格式/枚举/默认与禁用条件),不是注释
    hint: str = ""


class ParamOutput(BaseModel):
    """一个输出列。运行时只能减,不能加、不能改表达式。"""

    model_config = ConfigDict(extra="allow")

    param_id: str
    expr: str
    alias: str
    source: str | None = None
    business_name: str = ""
    hint: str = ""


class ParamGroupBy(BaseModel):
    """一个分组维度。减掉它时 `linked_output` 那一列必须同时减(应用器强制)。"""

    model_config = ConfigDict(extra="allow")

    param_id: str
    expr: str
    source: str | None = None
    linked_output: str | None = None
    business_name: str = ""
    hint: str = ""


class IntentParams(BaseModel):
    """三区参数 = **运行时权力的完整清单**。字段级定义见 DB-DESIGN §4.8。"""

    filters: list[ParamFilter] = []
    outputs: list[ParamOutput] = []
    groupbys: list[ParamGroupBy] = []


class IntentQuestionOut(ORMModel):
    id: uuid.UUID
    question_text: str
    origin: str


class SqlIntentOut(ORMModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    datasource_id: uuid.UUID
    #: 人可读的稳定短标识(i01…):trace / 评审报告 / 评测集都引它
    code: str
    intent_type: str
    bucket: str | None = None
    one_liner: str
    brief: str
    tables: list[str] = []
    status: str
    human_edited: bool
    prefill_rounds: int
    published_at: datetime | None = None
    source_staging_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    # 列表页要的派生量
    question_count: int = 0
    face_count: int = 0
    has_sql: bool = False


class SqlIntentDetail(SqlIntentOut):
    sql: str | None = None
    params: IntentParams = IntentParams()
    questions: list[IntentQuestionOut] = []
    #: 空列表 = 可以发布。非空时每条都是**发布按钮变灰的原因**,直接显示给用户
    publish_blockers: list[str] = []


class IntentCreate(BaseModel):
    """手工新建一个意图(D3 的"手工新建")。建出来是 draft,SQL 与参数区随后再做。"""

    intent_type: Literal["query", "stats"]
    one_liner: str = Field(min_length=1, max_length=300)
    brief: str = Field(min_length=1)
    tables: list[str] = Field(min_length=1)
    bucket: str | None = None
    kb_id: uuid.UUID | None = None
    datasource_id: uuid.UUID | None = None


class IntentUpdate(BaseModel):
    """就地编辑。**任何一次带内容的 PATCH 都会把 `human_edited` 置 true** ——
    "这条被人改过"是评审材料里必须留的痕。"""

    intent_type: Literal["query", "stats"] | None = None
    one_liner: str | None = Field(default=None, min_length=1, max_length=300)
    brief: str | None = Field(default=None, min_length=1)
    tables: list[str] | None = None
    bucket: str | None = None
    sql: str | None = None
    params: IntentParams | None = None


class DesignMeasure(BaseModel):
    """一个度量的表达式与口径。"""

    model_config = ConfigDict(extra="allow")

    expr: str = ""
    meaning: str = ""


class DesignFilter(BaseModel):
    """模板里写死的一个默认过滤条件。`why` 是它凭什么被写死 —— 评审就看这一句。"""

    model_config = ConfigDict(extra="allow")

    column: str = ""
    operator: str = ""
    value: str = ""
    why: str = ""


class TemplateDesign(BaseModel):
    """★ 生成器的结构化设计说明:join 路径 / 度量口径 / 分组维度 / 默认过滤及其理由。

    它是**评审材料**,不是给用户看的提示文案 —— 形状由 `template.py` 的
    结构化输出 schema 冻结(那边 measures/group_by_dims 允许 null),所以这里逐项可空。
    """

    model_config = ConfigDict(extra="allow")

    join_path: str | None = None
    measures: list[DesignMeasure] | None = None
    group_by_dims: list[str] | None = None
    default_filters: list[DesignFilter] | None = None
    caliber_notes: list[str] | None = None


class TemplateResult(BaseModel):
    """AI 生成模板的返回:SQL + 参数区 + **试执行结果**。

    试执行不是附赠品:模板生成器的通过条件之一就是"在真库上跑得出非空结果",
    所以这里返回的 trial 是它已经跑过的那一次,不是前端另外发起的。
    """

    intent: SqlIntentDetail
    design: TemplateDesign = TemplateDesign()
    repair_rounds: int = 0
    prefill_rounds: int = 0
    trial_cols: list[str] = []
    trial_rows: list[list[object]] = []
    trial_rowcount: int = 0


class RunRequest(BaseModel):
    """在意图详情页试跑一条 SQL。不传 sql 就跑意图当前存着的那条。"""

    sql: str | None = None


class RunResult(BaseModel):
    """★ Run 走的是**运行时那一道执行闸**(单条 SELECT / 白名单 / 强制 LIMIT / 超时)。

    所以"Run 过了"这件事的含义是明确的:它在运行时不会因为闸而失败。
    `sql_executed` 是闸改写后真正发给数据库的那条(LIMIT 可能被它压过)。
    """

    ok: bool
    sql_executed: str | None = None
    cols: list[str] = []
    rowcount: int = 0
    rows: list[list[object]] = []
    flags: list[str] = []
    error: str | None = None


class ParseParamsResult(BaseModel):
    """按当前 SQL 重解析参数区。`kept_annotations` = 按 param_id 保住的 业务名/hint 条数。"""

    params: IntentParams
    kept_annotations: int = 0


class GenerateIntentsRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=30)
    tables: list[str] | None = None


class QuestionsGenerated(BaseModel):
    """AI 生成的相似问法**建议**(未落库)。`dropped` 是被跨意图冲突过滤掉的。"""

    questions: list[str] = []
    dropped: list[dict] = []


class QuestionsSave(BaseModel):
    """整组替换(不做逐条 diff)。已发布的意图保存后立即重建索引面。"""

    questions: list[str] = Field(max_length=50)


class QuestionsSaveResult(BaseModel):
    questions: list[IntentQuestionOut]
    #: 重建出来的索引面数;意图还是 draft 时为 0(draft 不进检索)
    faces: int = 0


class IntentPublishResult(BaseModel):
    intent_id: uuid.UUID
    code: str
    status: str
    faces: int = 0
    non_data_faces: int = 0


# ============================================================ 空路由负例面


class NonDataFaceOut(ORMModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    face_text: str
    origin: str
    enabled: bool


class NonDataFacesSave(BaseModel):
    """整组替换本 kb 的负例面,保存即重建。

    ★ 这不是"可选的调优项":非问数问题靠"索引里有更像的负例"拦下,靠阈值拦不住
    (B8 实测,见 `services/text2sql/architect.md` §4)。清空它等于关掉空路由。
    """

    faces: list[str] = Field(max_length=100)


class NonDataFacesSaveResult(BaseModel):
    faces: list[NonDataFaceOut]
    indexed: int = 0


class IndexStats(BaseModel):
    """索引体检:各类面各有多少。`summary + question + non_data` 就是检索的全部输入。"""

    kb_id: uuid.UUID
    summary: int = 0
    question: int = 0
    non_data: int = 0
    total: int = 0
    published_intents: int = 0
