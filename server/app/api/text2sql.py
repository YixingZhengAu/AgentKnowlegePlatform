"""智能问数(S3)的 REST 接口:数据源 → Schema 治理 → 意图与模板 → 发布。

**候选意图的列表与编辑不在这里** —— 它们走 S0 的通用审核接口
(`GET /api/staging?job_id=`、`POST /api/staging/bulk`),因为"筛选/编辑/批量采纳"
对三类知识是同一套流程。本文件只放 S3 独有的动作:

| 动作 | 端点 | 为什么不能通用化 |
| --- | --- | --- |
| 数据源 CRUD / 测连 | `/datasources…` | 口令要加密、要能先测再存 |
| Schema 治理读写 | `/datasources/{id}/schema`、`PUT /tables/{id}` | 审描述要同屏看采样值与枚举 |
| 三件套 AI 生成 | `…/sync`、`…/describe`、`…/intents`、`…/template` | 批量走 Job,单点同步返回 |
| 模板 Run | `POST /intents/{id}/run` | 审的是"这条 SQL 出的数对不对" |
| 相似问法 / 负例面 | `PUT …/questions`、`PUT /non-data-faces` | 保存即重建索引面 |
| 发布 / 下线 | `POST /intents/{id}/publish` | **采纳 ≠ 发布**,发布才建索引面 |

★ 三条贯穿全文件的纪律:
1. **口令进不出**:入参收到明文立刻 Fernet 加密落库,任何出参只回 host/port/user/database;
2. **贵的活分两种**:批量(每表一次 gpt-5)一律派 Job 让页面可以离开,单点(一条模板)
   同步返回 —— 前者轮询 `GET /api/jobs/{id}`,后者直接等;
3. **要连客户库的动作都先查 `readonly_confirmed`**;测连是唯一例外(不测怎么确认)。
"""

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import ConflictError, NotFoundError
from app.core.jobs import execute_job, submit_job
from app.core.logging import get_logger
from app.models import (
    ColumnMeta,
    Datasource,
    IntentQuestion,
    IntentVector,
    KnowledgeBase,
    NonDataFace,
    Relation,
    SqlIntent,
    StagingItem,
    TableMeta,
)
from app.schemas.common import ListResponse
from app.schemas.text2sql import (
    ColumnSuggestion,
    DatasourceCreate,
    DatasourceOut,
    DatasourceUpdate,
    DescribeRequest,
    DescribeSuggestion,
    GenerateIntentsRequest,
    IndexStats,
    IntentCreate,
    IntentParams,
    IntentPublishResult,
    IntentQuestionOut,
    IntentUpdate,
    JobStarted,
    NonDataFaceOut,
    NonDataFacesSave,
    NonDataFacesSaveResult,
    ParseParamsResult,
    QuestionsGenerated,
    QuestionsSave,
    QuestionsSaveResult,
    RelationOut,
    RunRequest,
    RunResult,
    SchemaOut,
    SqlIntentDetail,
    SqlIntentOut,
    TableDetailOut,
    TableSave,
    TemplateResult,
    TestConnectionResult,
)
from app.schemas.text2sql import DatasourceConnIn as ConnIn
from app.services.text2sql import bizdb, executor, indexer, introspect, publisher, semantic
from app.services.text2sql import params as param_svc
from app.services.text2sql import questions as question_svc
from app.services.text2sql import template as template_svc

router = APIRouter(prefix="/api/text2sql", tags=["text2sql"])
log = get_logger(__name__)

#: Run 面板回带的行数。比运行时 trace 的 5 行多 —— 人要靠它判断"数对不对"
RUN_PREVIEW_ROWS = 25


# ================================================================ 公共装载


async def _default_kb(session: SessionDep) -> KnowledgeBase:
    kb = (
        await session.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.type == "text2sql", KnowledgeBase.status == "active")
            .order_by(KnowledgeBase.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if kb is None:
        raise NotFoundError(
            "No text2sql knowledge base found, run `make seed`", code="kb_missing"
        )
    return kb


async def _get_datasource(session: SessionDep, datasource_id: uuid.UUID) -> Datasource:
    ds = await session.get(Datasource, datasource_id)
    if ds is None:
        raise NotFoundError(f"Datasource {datasource_id} not found")
    return ds


def _live_conn(ds: Datasource) -> bizdb.BizConn:
    """解出连接要素。**这里是 readonly 闸门**:没确认过只读的数据源一律不连。

    不是"提示",是拒 —— 一个可写账号接进来,后面四道安全关就少了最硬的那一道。
    """
    if not ds.readonly_confirmed:
        raise ConflictError(
            "This datasource is not confirmed read-only. Confirm the account only has "
            "SELECT privileges before running anything against it.",
            code="datasource_not_readonly",
        )
    return bizdb.parse_dsn(bizdb.decrypt_dsn(ds.dsn_enc))


async def _ds_out(session: SessionDep, ds: Datasource) -> DatasourceOut:
    """出参组装。治理进度在这里数一次 —— 让前端拉全量 schema 再数会贵得多。"""
    conn = bizdb.parse_dsn(bizdb.decrypt_dsn(ds.dsn_enc))
    tables = (
        await session.execute(
            select(
                func.count(),
                func.count(TableMeta.id).filter(TableMeta.enabled.is_(True)),
                func.count(TableMeta.id).filter(TableMeta.description.isnot(None)),
            ).where(TableMeta.datasource_id == ds.id)
        )
    ).one()
    intents = (
        await session.execute(
            select(func.count())
            .select_from(SqlIntent)
            .where(SqlIntent.datasource_id == ds.id, SqlIntent.status == "published")
        )
    ).scalar_one()
    return DatasourceOut(
        id=ds.id,
        kb_id=ds.kb_id,
        name=ds.name,
        db_type=ds.db_type,
        status=ds.status,
        readonly_confirmed=ds.readonly_confirmed,
        host=conn.host,
        port=conn.port,
        database=conn.database,
        user=conn.user,
        last_synced_at=ds.last_synced_at,
        tables=tables[0],
        enabled_tables=tables[1],
        described_tables=tables[2],
        published_intents=intents,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


# ================================================================ 数据源


@router.get("/datasources", response_model=ListResponse[DatasourceOut])
async def list_datasources(
    session: SessionDep, kb_id: uuid.UUID | None = None
) -> ListResponse:
    kb_id = kb_id or (await _default_kb(session)).id
    rows = (
        await session.scalars(
            select(Datasource)
            .where(Datasource.kb_id == kb_id)
            .order_by(Datasource.created_at)
        )
    ).all()
    items = [await _ds_out(session, ds) for ds in rows]
    return ListResponse[DatasourceOut](items=items, total=len(items))


@router.post("/datasources", response_model=DatasourceOut, status_code=201)
async def create_datasource(
    req: DatasourceCreate, session: SessionDep
) -> DatasourceOut:
    """新建数据源。连接串在这里被加密,**明文不再出现在任何地方**。"""
    kb = await session.get(KnowledgeBase, req.kb_id) if req.kb_id else await _default_kb(session)
    if kb is None:
        raise NotFoundError(f"Knowledge base {req.kb_id} not found")
    dup = (
        await session.scalars(
            select(Datasource).where(Datasource.kb_id == kb.id, Datasource.name == req.name)
        )
    ).first()
    if dup is not None:
        raise ConflictError(
            f"A datasource named '{req.name}' already exists", code="datasource_name_taken"
        )
    ds = Datasource(
        kb_id=kb.id,
        name=req.name,
        db_type=req.db_type,
        dsn_enc=bizdb.encrypt_dsn(bizdb.build_dsn(_conn_of(req.conn))),
        readonly_confirmed=req.readonly_confirmed,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    log.info("datasource_created", datasource_id=str(ds.id), target=_conn_of(req.conn).masked())
    return await _ds_out(session, ds)


def _conn_of(conn: ConnIn) -> bizdb.BizConn:
    return bizdb.BizConn(
        host=conn.host,
        port=conn.port,
        user=conn.user,
        password=conn.password,
        database=conn.database,
    )


@router.get("/datasources/{datasource_id}", response_model=DatasourceOut)
async def get_datasource(datasource_id: uuid.UUID, session: SessionDep) -> DatasourceOut:
    return await _ds_out(session, await _get_datasource(session, datasource_id))


@router.patch("/datasources/{datasource_id}", response_model=DatasourceOut)
async def update_datasource(
    datasource_id: uuid.UUID, req: DatasourceUpdate, session: SessionDep
) -> DatasourceOut:
    """改数据源。传了 `conn` 就是整套换掉(口令不可能"部分更新")。"""
    ds = await _get_datasource(session, datasource_id)
    if req.name is not None:
        ds.name = req.name
    if req.conn is not None:
        ds.dsn_enc = bizdb.encrypt_dsn(bizdb.build_dsn(_conn_of(req.conn)))
    if req.readonly_confirmed is not None:
        ds.readonly_confirmed = req.readonly_confirmed
    if req.status is not None:
        ds.status = req.status
    await session.commit()
    await session.refresh(ds)
    return await _ds_out(session, ds)


@router.delete("/datasources/{datasource_id}", status_code=204)
async def delete_datasource(datasource_id: uuid.UUID, session: SessionDep) -> None:
    """删一个数据源(级联带走它的语义层:表/列/join)。

    **挂着意图的数据源不许删**(409):意图的模板 SQL 是这个库的表名与方言写的,
    删了数据源那些模板就再也跑不起来,而它们可能已经被历史消息的引用指过。
    要清掉这类数据源,先把它的意图逐条下线并删掉 —— 那是个显式动作,
    不该由"删数据源"顺手替人做。

    这是给演示现场准备的:填错连接、接错库能自己清掉,不用去翻数据库。
    """
    ds = await _get_datasource(session, datasource_id)
    n = (
        await session.execute(
            select(func.count())
            .select_from(SqlIntent)
            .where(SqlIntent.datasource_id == ds.id)
        )
    ).scalar_one()
    if n:
        raise ConflictError(
            f"This datasource has {n} intent(s) attached; remove them first",
            code="datasource_has_intents",
        )
    await session.delete(ds)
    await session.commit()
    log.info("datasource_deleted", datasource_id=str(datasource_id))


@router.post("/datasources/test", response_model=TestConnectionResult)
async def test_new_connection(conn: ConnIn) -> TestConnectionResult:
    """测一套**还没保存**的连接要素(D1 的"先测再存")。

    连不上返回 `ok=false` 而不是 4xx:连不上是这个接口要报告的**业务结果**,
    不是调用方用错了接口。前端据此在表单上显示红字,不用去解析错误码。
    """
    return TestConnectionResult(**await bizdb.test_connection(_conn_of(conn)))


@router.post("/datasources/{datasource_id}/test", response_model=TestConnectionResult)
async def test_datasource(
    datasource_id: uuid.UUID, session: SessionDep
) -> TestConnectionResult:
    """测一个已保存的数据源。**不查 readonly_confirmed** —— 测连正是确认它的手段。"""
    ds = await _get_datasource(session, datasource_id)
    conn = bizdb.parse_dsn(bizdb.decrypt_dsn(ds.dsn_enc))
    return TestConnectionResult(**await bizdb.test_connection(conn))


@router.post("/datasources/{datasource_id}/sync", response_model=JobStarted)
async def sync_schema(
    datasource_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
) -> JobStarted:
    """同步库表结构(`t2s_sync_schema`)。零 LLM,随时可重跑 —— 库变了就该跑一次。

    **只覆盖物理事实**(类型/注释/采样/枚举/join),治理字段(description/enabled/
    is_sensitive)一个字都不碰。所以"同步会不会把我改的描述冲掉"的答案是:不会。
    """
    ds = await _get_datasource(session, datasource_id)
    _live_conn(ds)  # 提前抛:连不上/没确认只读的话,不该先建出一个必然失败的 Job
    return await _dispatch(background, "t2s_sync_schema", ds, user, {})


@router.post("/datasources/{datasource_id}/describe", response_model=JobStarted)
async def describe_schema(
    datasource_id: uuid.UUID,
    req: DescribeRequest,
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
) -> JobStarted:
    """批量写表/列描述(`t2s_describe`)。**每张启用的表一次 gpt-5**,所以走 Job。"""
    ds = await _get_datasource(session, datasource_id)
    _live_conn(ds)
    return await _dispatch(
        background, "t2s_describe", ds, user, {"mode": req.mode, "tables": req.tables}
    )


@router.post("/datasources/{datasource_id}/intents", response_model=JobStarted)
async def generate_intents(
    datasource_id: uuid.UUID,
    req: GenerateIntentsRequest,
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
) -> JobStarted:
    """批量提意图候选(`t2s_intents`)→ 审核台。终态 `review`,等人采纳。

    再点一次就是**追加生成**:已有意图的 one-liner 会被喂回 prompt 要求避重
    (在源头防重复,比事后判重便宜 —— 判重只能告诉你钱已经花了)。
    """
    ds = await _get_datasource(session, datasource_id)
    _live_conn(ds)
    return await _dispatch(
        background, "t2s_intents", ds, user, {"count": req.count, "tables": req.tables}
    )


async def _dispatch(
    background: BackgroundTasks,
    job_type: str,
    ds: Datasource,
    user: CurrentUser,
    extra: dict,
) -> JobStarted:
    """建 Job 再派发。**`params` 里只放 datasource_id** —— 它会落库并出现在接口响应里,
    连接串明文绝不能进它(解密在 Job 的 prepare 里做,只活在进程内存)。"""
    job = await submit_job(
        job_type=job_type,
        kb_id=ds.kb_id,
        params={"datasource_id": str(ds.id), **{k: v for k, v in extra.items() if v is not None}},
        created_by=user.id,
    )
    background.add_task(execute_job, job.id)
    log.info("text2sql_job_dispatched", job_type=job_type, job_id=str(job.id))
    return JobStarted(job_id=job.id, job_type=job_type)


# ================================================================ Schema 治理


def _enum_out(raw: list | None) -> list[dict] | None:
    """枚举字典兼容两种历史形态:`["NSW"]` 与 `[{"value","meaning"}]`,出参统一成后者。"""
    if not raw:
        return None
    out = []
    for v in raw:
        out.append(v if isinstance(v, dict) else {"value": str(v), "meaning": None})
    return out


def _column_out(cm: ColumnMeta) -> dict:
    d = {c: getattr(cm, c) for c in (
        "id", "column_name", "ordinal", "data_type", "is_nullable", "key_flag",
        "physical_comment", "display_name", "description", "is_sensitive",
        "distinct_count", "is_enum_like", "sample_values", "enabled")}
    d["enum_values"] = _enum_out(cm.enum_values)
    d["sample_values"] = [str(v) for v in (cm.sample_values or [])] or None
    return d


async def _table_detail(session: SessionDep, tm: TableMeta) -> TableDetailOut:
    cols = (
        await session.scalars(
            select(ColumnMeta)
            .where(ColumnMeta.table_meta_id == tm.id)
            .order_by(ColumnMeta.ordinal, ColumnMeta.column_name)
        )
    ).all()
    return TableDetailOut(
        **{c: getattr(tm, c) for c in (
            "id", "datasource_id", "schema_name", "table_name", "display_name",
            "description", "physical_comment", "enabled", "row_count_estimate")},
        column_count=len(cols),
        described_columns=sum(1 for c in cols if (c.description or "").strip()),
        columns=[_column_out(c) for c in cols],
    )


@router.get("/datasources/{datasource_id}/schema", response_model=SchemaOut)
async def get_schema(datasource_id: uuid.UUID, session: SessionDep) -> SchemaOut:
    """治理页一次拿全:数据源 + 表(含列、采样值、枚举字典)+ join 提示。

    **停用的表列也返回** —— 治理页要能把它们勾回来。运行时的语义层才按 enabled 过滤
    (`semantic.load_layer`),那是同一个开关的另一端。
    """
    ds = await _get_datasource(session, datasource_id)
    tables = (
        await session.scalars(
            select(TableMeta)
            .where(TableMeta.datasource_id == ds.id)
            .order_by(TableMeta.table_name)
        )
    ).all()
    rels = (
        await session.scalars(
            select(Relation)
            .where(Relation.datasource_id == ds.id)
            .order_by(Relation.from_table, Relation.from_column)
        )
    ).all()
    return SchemaOut(
        datasource=await _ds_out(session, ds),
        tables=[await _table_detail(session, tm) for tm in tables],
        relations=[RelationOut.model_validate(r) for r in rels],
    )


async def _get_table(session: SessionDep, table_meta_id: uuid.UUID) -> TableMeta:
    tm = await session.get(TableMeta, table_meta_id)
    if tm is None:
        raise NotFoundError(f"Table {table_meta_id} not found")
    return tm


@router.put("/tables/{table_meta_id}", response_model=TableDetailOut)
async def save_table(
    table_meta_id: uuid.UUID, req: TableSave, session: SessionDep
) -> TableDetailOut:
    """按表保存(D2 的 Save):表级字段 + 若干列,**一个事务**。

    整表一次提交而不是逐格 PATCH:审描述是"看完一张表再存"的动作,逐格保存会把
    一次人工评审拆成几十个请求,中途失败还会留下半改的表。
    """
    tm = await _get_table(session, table_meta_id)
    if req.display_name is not None:
        tm.display_name = req.display_name
    if req.description is not None:
        tm.description = req.description
    if req.enabled is not None:
        tm.enabled = req.enabled
    ids = [c.id for c in req.columns]
    owned = set(
        (
            await session.scalars(
                select(ColumnMeta.id).where(
                    ColumnMeta.table_meta_id == tm.id, ColumnMeta.id.in_(ids)
                )
            )
        ).all()
    ) if ids else set()
    for patch in req.columns:
        if patch.id not in owned:
            # 别的表的列不许从这里改:否则一次"保存 orders"能悄悄改掉 customers
            raise ConflictError(
                f"Column {patch.id} does not belong to table {tm.table_name}",
                code="column_not_in_table",
            )
        cm = await session.get(ColumnMeta, patch.id)
        for field in ("display_name", "description", "is_sensitive", "enabled"):
            v = getattr(patch, field)
            if v is not None:
                setattr(cm, field, v)
    await session.commit()
    log.info("text2sql_table_saved", table=tm.table_name, columns=len(req.columns))
    return await _table_detail(session, tm)


@router.post("/tables/{table_meta_id}/describe", response_model=DescribeSuggestion)
async def describe_table(
    table_meta_id: uuid.UUID, req: DescribeRequest, session: SessionDep
) -> DescribeSuggestion:
    """单点 AI 生成一张表的描述,**同步返回建议、不落库**(人确认后走 `PUT /tables/{id}`)。

    ★ 为什么单列的"AI 按钮"也要整表生成:评审过的 prompt 是**表级**的 ——
    它靠同表其他列、join 关系和采样值一起判断一列是什么。只喂一列会得到更差的描述,
    而那就不再是 B2 验收过的那个 prompt 了。前端拿到整表建议,回填哪一格由它决定。
    """
    tm = await _get_table(session, table_meta_id)
    ds = await _get_datasource(session, tm.datasource_id)
    conn = _live_conn(ds)
    snap = await asyncio.to_thread(introspect.build_snapshot, conn)
    entry = await semantic.describe_table(snap, tm.table_name, mode=req.mode)
    return DescribeSuggestion(
        table_name=tm.table_name,
        description=entry.get("description", ""),
        columns=[
            ColumnSuggestion(
                column_name=c["name"],
                display_name=c.get("display_name", ""),
                description=c.get("description", ""),
                enum_values=_enum_out(c.get("enum_values")),
            )
            for c in entry.get("columns", [])
        ],
    )


# ================================================================ 意图


async def _get_intent(session: SessionDep, intent_id: uuid.UUID) -> SqlIntent:
    it = await session.get(SqlIntent, intent_id)
    if it is None:
        raise NotFoundError(f"Intent {intent_id} not found")
    return it


async def _questions(session: SessionDep, intent_id: uuid.UUID) -> list[IntentQuestion]:
    return list(
        (
            await session.scalars(
                select(IntentQuestion)
                .where(IntentQuestion.intent_id == intent_id)
                .order_by(IntentQuestion.created_at, IntentQuestion.question_text)
            )
        ).all()
    )


async def _intent_out(session: SessionDep, it: SqlIntent) -> SqlIntentOut:
    counts = (
        await session.execute(
            select(
                select(func.count())
                .select_from(IntentQuestion)
                .where(IntentQuestion.intent_id == it.id)
                .scalar_subquery(),
                select(func.count())
                .select_from(IntentVector)
                .where(IntentVector.intent_id == it.id)
                .scalar_subquery(),
            )
        )
    ).one()
    return SqlIntentOut(
        **{c: getattr(it, c) for c in (
            "id", "kb_id", "datasource_id", "code", "intent_type", "bucket", "one_liner",
            "brief", "tables", "status", "human_edited", "prefill_rounds", "published_at",
            "source_staging_id", "created_at", "updated_at")},
        question_count=counts[0],
        face_count=counts[1],
        has_sql=bool((it.sql or "").strip()),
    )


async def _intent_detail(session: SessionDep, it: SqlIntent) -> SqlIntentDetail:
    base = await _intent_out(session, it)
    return SqlIntentDetail(
        **base.model_dump(),
        sql=it.sql,
        params=IntentParams.model_validate(it.params or {}),
        questions=[IntentQuestionOut.model_validate(q) for q in await _questions(session, it.id)],
        publish_blockers=publisher.publish_blockers(it),
    )


@router.get("/intents", response_model=ListResponse[SqlIntentOut])
async def list_intents(
    session: SessionDep,
    kb_id: uuid.UUID | None = None,
    status: Annotated[str | None, Query(pattern="^(draft|published|disabled)$")] = None,
) -> ListResponse:
    kb_id = kb_id or (await _default_kb(session)).id
    stmt = select(SqlIntent).where(SqlIntent.kb_id == kb_id).order_by(SqlIntent.code)
    if status is not None:
        stmt = stmt.where(SqlIntent.status == status)
    rows = (await session.scalars(stmt)).all()
    items = [await _intent_out(session, it) for it in rows]
    return ListResponse[SqlIntentOut](items=items, total=len(items))


@router.post("/intents", response_model=SqlIntentDetail, status_code=201)
async def create_intent(req: IntentCreate, session: SessionDep) -> SqlIntentDetail:
    """手工新建一个意图(D3 的"手工新建")。建出来是 **draft** —— 和采纳候选一样,
    "这类问题值得做成模板"和"这条模板我验收了"是两件事。"""
    kb = await session.get(KnowledgeBase, req.kb_id) if req.kb_id else await _default_kb(session)
    if kb is None:
        raise NotFoundError(f"Knowledge base {req.kb_id} not found")
    ds_id = req.datasource_id
    if ds_id is None:
        ds = (
            await session.scalars(
                select(Datasource)
                .where(Datasource.kb_id == kb.id, Datasource.status == "active")
                .order_by(Datasource.created_at)
            )
        ).first()
        if ds is None:
            raise ConflictError(
                "This knowledge base has no active datasource to attach the intent to",
                code="datasource_missing",
            )
        ds_id = ds.id
    it = SqlIntent(
        kb_id=kb.id,
        datasource_id=ds_id,
        code=await publisher.next_code(session, kb.id),
        intent_type=req.intent_type,
        bucket=req.bucket,
        one_liner=req.one_liner.strip(),
        brief=req.brief.strip(),
        tables=req.tables,
        status="draft",
        human_edited=True,
    )
    session.add(it)
    await session.commit()
    await session.refresh(it)
    return await _intent_detail(session, it)


@router.get("/intents/{intent_id}", response_model=SqlIntentDetail)
async def get_intent(intent_id: uuid.UUID, session: SessionDep) -> SqlIntentDetail:
    return await _intent_detail(session, await _get_intent(session, intent_id))


@router.patch("/intents/{intent_id}", response_model=SqlIntentDetail)
async def update_intent(
    intent_id: uuid.UUID, req: IntentUpdate, session: SessionDep
) -> SqlIntentDetail:
    """就地编辑(含直接改 SQL 与参数区)。

    ★ **已发布的意图改了 SQL/参数区,不会自动重新发布** —— 索引面挂的是问法与摘要,
    改 SQL 不影响检索,但改完必须自己 Run 一遍再点发布。改摘要会影响检索,
    所以那一路会重建索引面(见下)。
    """
    it = await _get_intent(session, intent_id)
    fields = req.model_dump(exclude_unset=True)
    if not fields:
        return await _intent_detail(session, it)
    summary_changed = "one_liner" in fields and fields["one_liner"] != it.one_liner
    for k, v in fields.items():
        if k == "params" and v is not None:
            it.params = IntentParams.model_validate(v).model_dump()
        elif v is not None:
            setattr(it, k, v.strip() if isinstance(v, str) else v)
    it.human_edited = True
    faces = 0
    if summary_changed and it.status == "published":
        # 摘要是索引面之一,改了就得重建 —— 否则检索还在用旧文本,界面上完全看不出来
        faces = await indexer.rebuild_intent_faces(session, it)
    await session.commit()
    await session.refresh(it)
    log.info("sql_intent_updated", intent=it.code, fields=sorted(fields), faces=faces)
    return await _intent_detail(session, it)


async def _layer_and_conn(session: SessionDep, it: SqlIntent) -> tuple[dict, bizdb.BizConn]:
    ds = await _get_datasource(session, it.datasource_id)
    conn = _live_conn(ds)
    layer = await semantic.load_layer(session, ds.id)
    if not layer["tables"]:
        raise ConflictError(
            "The semantic layer is empty — sync and describe the schema first",
            code="semantic_layer_empty",
        )
    return layer, conn


def _intent_dict(it: SqlIntent) -> dict:
    """意图行 → 生成期各模块吃的意图字典。`id` 用 code(评审材料里要能认得出是哪条)。"""
    return {
        "id": it.code,
        "intent_id": it.code,
        "type": it.intent_type,
        "bucket": it.bucket,
        "one_liner": it.one_liner,
        "brief": it.brief,
        "tables": list(it.tables or []),
    }


@router.post("/intents/{intent_id}/template", response_model=TemplateResult)
async def generate_template(intent_id: uuid.UUID, session: SessionDep) -> TemplateResult:
    """★ 生成 SQL 模板 + 参数区,**同步返回**(一次意图一次,慢且贵:gpt-5 数次调用)。

    走完的是 B4 + B5 的完整链路,一步都没省:
    生成 → 9 条确定性静态校验 → **真库试执行** → 报错回灌自修 ≤2 轮 → AST 拆三区参数
    → AI 预填 business_name/hint → 校验回灌 ≤2 轮。所以它返回时,这条 SQL 已经在真库上
    跑出过非空结果 —— `trial_*` 就是那一次的结果,不是前端另外发起的。

    覆盖已有的 SQL:重生成会**整条替换** sql 与 params(人工改过的 hint 也会没)。
    这是"重新生成"的应有语义,前端要在按钮上说清楚。
    """
    it = await _get_intent(session, intent_id)
    layer, conn = await _layer_and_conn(session, it)
    template = await template_svc.generate_template(conn, layer, _intent_dict(it))
    package = await param_svc.build_package(template, layer)
    it.sql = template["sql"]
    it.params = package["params"]
    it.prefill_rounds = package["prefill_rounds"]
    await session.commit()
    await session.refresh(it)
    trial = template["trial"]
    log.info("sql_template_generated", intent=it.code, repair_rounds=template["repair_rounds"])
    return TemplateResult(
        intent=await _intent_detail(session, it),
        design=template.get("design") or {},
        repair_rounds=template["repair_rounds"],
        prefill_rounds=package["prefill_rounds"],
        trial_cols=trial["columns"],
        trial_rows=trial["rows_preview"],
        trial_rowcount=trial["row_count"],
    )


@router.post("/intents/{intent_id}/parse-params", response_model=ParseParamsResult)
async def parse_params(intent_id: uuid.UUID, session: SessionDep) -> ParseParamsResult:
    """按当前 SQL 重解析参数区(D4:改完 SQL 参数区要跟着变)。**纯代码,零 LLM。**

    按 `param_id` 保住人写过的 business_name/hint —— 改一处 WHERE 值不该让整页注释重写。
    对不上的参数(列换了、谓词删了)就是新的,注释留空等 AI 预填或人手写。
    """
    it = await _get_intent(session, intent_id)
    if not (it.sql or "").strip():
        raise ConflictError("This intent has no SQL yet", code="sql_intent_no_sql")
    ds = await _get_datasource(session, it.datasource_id)
    layer = await semantic.load_layer(session, ds.id)
    try:
        skeleton = param_svc.parse_params(it.sql, layer)
    except (AssertionError, ValueError, KeyError) as exc:
        # 人手改坏了 SQL(投影没起别名、过滤列不在语义层)是常态,如实说清哪里不行
        raise ConflictError(
            f"Cannot parse the template's parameters: {exc}", code="params_unparsable"
        ) from exc
    old = {
        p["param_id"]: p
        for zone in (it.params or {}).values()
        if isinstance(zone, list)
        for p in zone
        if isinstance(p, dict)
    }
    kept = 0
    for zone in skeleton.values():
        for p in zone:
            prev = old.get(p["param_id"])
            if prev and (prev.get("business_name") or prev.get("hint")):
                p["business_name"] = prev.get("business_name", "")
                p["hint"] = prev.get("hint", "")
                kept += 1
    it.params = skeleton
    it.human_edited = True
    await session.commit()
    return ParseParamsResult(
        params=IntentParams.model_validate(skeleton), kept_annotations=kept
    )


@router.post("/intents/{intent_id}/run", response_model=RunResult)
async def run_template(
    intent_id: uuid.UUID, req: RunRequest, session: SessionDep
) -> RunResult:
    """★ 试跑一条 SQL。走的是**运行时那一道执行闸**,不是另开一条通路。

    所以"Run 过了"含义明确:它在运行时不会因为闸(非单条 SELECT / 表列不在语义层白名单 /
    LIMIT 超限 / 超时)而失败。被闸拒或 SQL 报错都返回 `ok=false` + 原因 ——
    在编辑器里改 SQL 本来就会写错,那是**这个接口要报告的结果**,不是接口调用错误。
    """
    it = await _get_intent(session, intent_id)
    sql = (req.sql or it.sql or "").strip()
    if not sql:
        raise ConflictError("Nothing to run: no SQL given and the intent has none",
                           code="sql_intent_no_sql")
    layer, conn = await _layer_and_conn(session, it)
    try:
        res = await executor.agate_and_execute(conn, sql, layer, preview=RUN_PREVIEW_ROWS)
    except Exception as exc:
        return RunResult(ok=False, error=str(exc))
    return RunResult(
        ok=True,
        sql_executed=res["sql_executed"],
        cols=res["cols"],
        rowcount=res["rowcount"],
        rows=[[_jsonable(v) for v in row] for row in res["sample"]],
        flags=res["flags"],
    )


def _jsonable(v: object) -> object:
    """Decimal / date / Decimal-in-tuple 之类直接进 JSON 会炸,统一落成 str。"""
    return v if v is None or isinstance(v, (bool, int, float, str)) else str(v)


@router.post("/intents/{intent_id}/publish", response_model=IntentPublishResult)
async def publish_intent(intent_id: uuid.UUID, session: SessionDep) -> IntentPublishResult:
    """发布:校验 → `status=published` → 重建索引面(意图的 + 本 kb 的空路由面)。

    一个事务。**向量写失败状态就不该改** —— 否则会留下一个"已发布但检索不到"的意图,
    而这种半残状态在界面上完全看不出来。
    """
    res = await publisher.publish_intent(session, intent_id)
    await session.commit()
    return IntentPublishResult(
        intent_id=uuid.UUID(res["intent_id"]),
        code=res["code"],
        status="published",
        faces=res["faces"],
        non_data_faces=res["non_data_faces"],
    )


@router.post("/intents/{intent_id}/disable", response_model=IntentPublishResult)
async def disable_intent(intent_id: uuid.UUID, session: SessionDep) -> IntentPublishResult:
    """下线:`status=disabled` + 删索引面。正式行留着 —— 它可能被历史消息的引用指过。"""
    res = await publisher.disable_intent(session, intent_id)
    await session.commit()
    return IntentPublishResult(
        intent_id=uuid.UUID(res["intent_id"]), code=res["code"], status=res["status"]
    )


@router.delete("/intents/{intent_id}", status_code=204)
async def delete_intent(intent_id: uuid.UUID, session: SessionDep) -> None:
    """删一个**草稿**意图(手工建错、采纳错了都用它)。

    已发布/已下线的不许删(409):它们可能被 `message_citations.ref_id` 指过,
    删了历史消息的引用就悬空 —— 与 S1 同一条纪律,下线用 `POST …/disable`。

    如果它是从候选采纳来的,这里会把那条候选的"已发布"标记撤掉,
    让它重新出现在审核台上 —— 那才是"采纳"的真正逆操作,不然会留下一条
    指向不存在意图的候选。
    """
    it = await _get_intent(session, intent_id)
    if it.status != "draft":
        raise ConflictError(
            f"Only draft intents can be deleted (this one is '{it.status}'); "
            "disable it instead",
            code="sql_intent_not_draft",
        )
    if it.source_staging_id is not None:
        staging = await session.get(StagingItem, it.source_staging_id)
        if staging is not None and (staging.published_ref or {}).get("id") == str(it.id):
            staging.published = False
            staging.published_ref = None
    await session.delete(it)
    await session.commit()
    log.info("sql_intent_deleted", intent=it.code)


# ================================================================ 相似问法


@router.get("/intents/{intent_id}/questions", response_model=ListResponse[IntentQuestionOut])
async def list_questions(intent_id: uuid.UUID, session: SessionDep) -> ListResponse:
    await _get_intent(session, intent_id)
    rows = await _questions(session, intent_id)
    return ListResponse[IntentQuestionOut](
        items=[IntentQuestionOut.model_validate(q) for q in rows], total=len(rows)
    )


@router.post("/intents/{intent_id}/questions/generate", response_model=QuestionsGenerated)
async def generate_questions(
    intent_id: uuid.UUID,
    session: SessionDep,
    n: Annotated[int, Query(ge=1, le=20)] = question_svc.DEFAULT_N,
) -> QuestionsGenerated:
    """AI 生成相似问法**建议**(未落库,人在页面上增删改后走 `PUT`)。

    两件不能省的事:
    * **喂真实取值**(`value_book`):B7 首轮没喂时,模型编出了 Perth/Adelaide 仓库和
      不存在的客户与产品 —— 相似问法是会进演示、会被人审的资产,编造值既误导审阅者,
      也教会路由器一堆库里没有的说法;
    * **跨意图文本冲突过滤**:撞上别的意图的摘要或已存问法的那句被丢掉并给出理由
      (`dropped`),不是静默扔掉 —— 界面要能解释"为什么只留下 6 条"。
    """
    it = await _get_intent(session, intent_id)
    layer, conn = await _layer_and_conn(session, it)
    siblings_rows = (
        await session.scalars(
            select(SqlIntent)
            .where(SqlIntent.kb_id == it.kb_id, SqlIntent.id != it.id,
                   SqlIntent.status != "disabled")
            .order_by(SqlIntent.code)
        )
    ).all()
    siblings = [
        {"intent_id": s.code, "one_liner": s.one_liner, "brief": s.brief,
         "tables": list(s.tables or []), "type": s.intent_type}
        for s in siblings_rows
    ]
    values = await asyncio.to_thread(question_svc.value_book, conn)
    raw = await question_svc.gen_one(_intent_dict(it), siblings, n, values)

    # 问题面 = 别的意图的摘要 + 它们已存的问法(与 B7 的 filter_questions 同一组谓词)
    faces: list[tuple[str, str]] = [(s.code, s.one_liner) for s in siblings_rows]
    for s in siblings_rows:
        for q in await _questions(session, s.id):
            faces.append((s.code, q.question_text))
    seen = {question_svc.normalize(it.one_liner)}
    kept: list[str] = []
    dropped: list[dict] = []
    for q in raw:
        if question_svc.normalize(q) in seen:
            dropped.append({"question": q,
                            "reason": "duplicate of the intent summary or an earlier question"})
            continue
        clash = question_svc.conflicting_face(q, it.code, faces)
        if clash:
            dropped.append({"question": q,
                            "reason": f'text conflict with {clash[0]}: "{clash[1]}"'})
            continue
        seen.add(question_svc.normalize(q))
        kept.append(q)
        faces.append((it.code, q))
    log.info("intent_questions_generated", intent=it.code, kept=len(kept), dropped=len(dropped))
    return QuestionsGenerated(questions=kept, dropped=dropped)


@router.put("/intents/{intent_id}/questions", response_model=QuestionsSaveResult)
async def save_questions(
    intent_id: uuid.UUID, req: QuestionsSave, session: SessionDep
) -> QuestionsSaveResult:
    """整组替换 + **保存即重建索引面**(意图已发布时)。

    不做逐条 diff:向量挂在 `intent_vectors` 而不是问法行上,正是为了不必处理
    "改一条、删一条、又加回来"的组合(见 `models/text2sql.py` 的 IntentQuestion 注释)。
    """
    it = await _get_intent(session, intent_id)
    texts: list[str] = []
    for q in req.questions:
        q = (q or "").strip()
        if q and q not in texts:
            texts.append(q)
    for old in await _questions(session, it.id):
        await session.delete(old)
    await session.flush()
    for q in texts:
        session.add(IntentQuestion(intent_id=it.id, question_text=q, origin="human"))
    await session.flush()
    faces = await indexer.rebuild_intent_faces(session, it)
    await session.commit()
    log.info("intent_questions_saved", intent=it.code, questions=len(texts), faces=faces)
    return QuestionsSaveResult(
        questions=[IntentQuestionOut.model_validate(q) for q in await _questions(session, it.id)],
        faces=faces,
    )


# ================================================================ 空路由负例面


@router.get("/non-data-faces", response_model=ListResponse[NonDataFaceOut])
async def list_non_data_faces(
    session: SessionDep, kb_id: uuid.UUID | None = None
) -> ListResponse:
    kb_id = kb_id or (await _default_kb(session)).id
    rows = (
        await session.scalars(
            select(NonDataFace)
            .where(NonDataFace.kb_id == kb_id)
            .order_by(NonDataFace.created_at, NonDataFace.face_text)
        )
    ).all()
    return ListResponse[NonDataFaceOut](
        items=[NonDataFaceOut.model_validate(f) for f in rows], total=len(rows)
    )


@router.put("/non-data-faces", response_model=NonDataFacesSaveResult)
async def save_non_data_faces(
    req: NonDataFacesSave, session: SessionDep, kb_id: uuid.UUID | None = None
) -> NonDataFacesSaveResult:
    """整组替换本 kb 的空路由负例面,保存即重建向量。

    ★ **这不是可选的调优项**:非问数问题是靠"索引里有更像的负例"拦下的,靠阈值拦不住
    (B8 实测:质保题以 0.5183 确信命中库存意图,而应命中类最低分 0.4981 ——
    抬阈值必先误杀真正例)。清空这一组等于关掉空路由,所以清空会返回 `indexed=0`
    并在服务端日志里留一条 warning。
    """
    kb_id = kb_id or (await _default_kb(session)).id
    texts: list[str] = []
    for f in req.faces:
        f = (f or "").strip()
        if f and f not in texts:
            texts.append(f)
    for old in (
        await session.scalars(select(NonDataFace).where(NonDataFace.kb_id == kb_id))
    ).all():
        await session.delete(old)
    await session.flush()
    for f in texts:
        session.add(NonDataFace(kb_id=kb_id, face_text=f, origin="human"))
    await session.flush()
    indexed = await indexer.rebuild_non_data_faces(session, kb_id)
    await session.commit()
    rows = (
        await session.scalars(
            select(NonDataFace)
            .where(NonDataFace.kb_id == kb_id)
            .order_by(NonDataFace.created_at, NonDataFace.face_text)
        )
    ).all()
    return NonDataFacesSaveResult(
        faces=[NonDataFaceOut.model_validate(f) for f in rows], indexed=indexed
    )


@router.get("/index-stats", response_model=IndexStats)
async def index_stats(session: SessionDep, kb_id: uuid.UUID | None = None) -> IndexStats:
    """索引体检:各类面各有多少。`summary + question + non_data` 就是检索的全部输入。"""
    kb_id = kb_id or (await _default_kb(session)).id
    size = await indexer.index_size(session, kb_id)
    return IndexStats(
        kb_id=kb_id,
        summary=size.get("summary", 0),
        question=size.get("question", 0),
        non_data=size.get("non_data", 0),
        total=size.get("faces", 0),
        published_intents=size.get("intents", 0),
    )
