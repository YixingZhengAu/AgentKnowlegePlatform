"""灌入 S3 智能问数的演示知识:数据源 + 语义层 + 12 个已验证意图 + 索引面。

用法:`uv run python -m scripts.seed_s3_demo`(幂等,重复跑不产生重复数据)
      `--rebuild-vectors` 只重建索引面(换过 embedding 型号/维度后用)

★ **为什么是 seed 而不是"跑一遍生成"**:这些是 Phase B 逐段人审签过字的治理资产
  (描述、模板 SQL、参数区 hint、相似问法、空路由负例面),不是随便生成一次就行的东西。
  重新生成一遍要花掉几十次 gpt-5 调用,而且**产出会和评审过的那一版不一样** ——
  于是 B8 评测集测出来的分数就不再指向被认可的那条链路了。
  生成能力本身在 `services/text2sql/{semantic,intents,template,params,questions}.py` 里,
  由三个 Job 与意图详情页驱动;这个脚本只负责把已认可的结果放回它该在的表。

★ 唯一在这里真花钱的一步是 embedding(≈120 条面,一次批量调用):向量不能从
  文件里"搬"过来 —— 它必须由当前 `.env` 里的 EMBEDDING_MODEL/DIM 现算,
  否则维度或型号一变,库里就是一堆静默错的向量。

流程:
  1. 找到 text2sql 类型的知识库(`seed_minimal` 建的 "Sales Analytics");
  2. 建/更新数据源(连接串取 `.env` 的 BIZ_DATABASE_URL,Fernet 加密后落 `dsn_enc`);
  3. 真跑一次 introspection 落语义层骨架(**物理事实必须来自真库**,不能来自文件);
  4. 把 B2 评审过的描述与枚举含义盖到治理字段上;
  5. 12 个意图(SQL + 参数区)落 `sql_intents`(published)+ 相似问法落 `intent_questions`;
  6. 12 条空路由负例面落 `non_data_faces`;
  7. 建索引面(`intent_vectors`)。
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Datasource,
    IntentQuestion,
    KnowledgeBase,
    NonDataFace,
    SqlIntent,
    TableMeta,
)
from app.services.text2sql import bizdb, indexer, introspect, semantic, sqltext

FIXTURES = Path(__file__).parent / "fixtures" / "s3"
DATASOURCE_NAME = "Company Sales (MySQL demo)"


def _load(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text())


async def _kb(session) -> KnowledgeBase:
    kb = (await session.scalars(
        select(KnowledgeBase).where(KnowledgeBase.type == "text2sql")
        .order_by(KnowledgeBase.created_at))).first()
    if kb is None:
        raise SystemExit("找不到 text2sql 类型的知识库。先跑:uv run python -m scripts.seed_minimal")
    return kb


async def _datasource(session, kb: KnowledgeBase) -> Datasource:
    conn = bizdb.demo_conn()
    ds = (await session.scalars(
        select(Datasource).where(Datasource.kb_id == kb.id,
                                 Datasource.name == DATASOURCE_NAME))).first()
    if ds is None:
        ds = Datasource(kb_id=kb.id, name=DATASOURCE_NAME)
        session.add(ds)
    ds.db_type = "mysql"
    # 每次 seed 都按当前 .env 重新加密:换过 SECRET_KEY 的机器上,旧密文是解不开的
    ds.dsn_enc = bizdb.encrypt_dsn(bizdb.build_dsn(conn))
    # 演示库的账号只有 SELECT 权限(docker/mysql/init/01-users.sql),这一条是运维确认位
    ds.readonly_confirmed = True
    ds.status = "active"
    await session.flush()
    return ds


async def _semantic_layer(session, ds: Datasource) -> dict:
    """真库 introspection 落骨架 → 盖上评审过的描述。返回计数。"""
    snap = await asyncio.to_thread(introspect.build_snapshot, bizdb.demo_conn())
    counts = await semantic.sync_schema(session, ds, snap)

    layer = _load("semantic_layer.json")
    described = 0
    for entry in layer["tables"]:
        tm = (await session.scalars(
            select(TableMeta).where(TableMeta.datasource_id == ds.id,
                                    TableMeta.table_name == entry["name"]))).first()
        if tm is None:
            print(f"  ! 语义层里有 {entry['name']},但库里没有这张表 —— 跳过")
            continue
        described += await semantic.save_descriptions(session, tm, entry)
    return {**counts, "described_columns": described}


async def _intents(session, kb: KnowledgeBase, ds: Datasource) -> dict:
    """意图 + 它们的相似问法(数量以 `fixtures/s3/intents/` 里的文件为准)。

    已存在的按 code 覆盖 —— seed 是幂等的,加一个意图就是往那个目录加一份 fixture。
    """
    n_intents = n_questions = 0
    for path in sorted((FIXTURES / "intents").glob("*.json")):
        pkg = json.loads(path.read_text())
        meta = pkg["intent"]
        code = meta["intent_id"]
        intent = (await session.scalars(
            select(SqlIntent).where(SqlIntent.kb_id == kb.id, SqlIntent.code == code))).first()
        if intent is None:
            intent = SqlIntent(kb_id=kb.id, datasource_id=ds.id, code=code,
                               intent_type=meta["type"], one_liner=meta["one_liner"],
                               brief=meta["brief"])
            session.add(intent)
        intent.datasource_id = ds.id
        intent.intent_type = meta["type"]
        intent.bucket = meta.get("bucket")
        intent.one_liner = meta["one_liner"]
        intent.brief = meta["brief"]
        intent.tables = list(meta["tables"])
        # fixture 里存的是 B4 评审定稿的原文(一行);排版留给代码做,
        # 免得评审过的产物文件被格式化改动搅进 diff(出处 `sqltext.py`)
        intent.sql = sqltext.format_sql(pkg["sql"])
        intent.params = pkg["params"]
        intent.prefill_rounds = pkg.get("prefill_rounds", 0)
        intent.human_edited = bool(pkg.get("human_edited"))
        intent.status = "published"
        intent.published_at = datetime.now(UTC)
        await session.flush()
        n_intents += 1

        qpath = FIXTURES / "questions" / f"{code}.json"
        if not qpath.exists():
            print(f"  ! {code} 没有相似问法文件 —— 它的索引面只有摘要一条")
            continue
        wanted = json.loads(qpath.read_text())["questions"]
        have = {q.question_text: q for q in (await session.scalars(
            select(IntentQuestion).where(IntentQuestion.intent_id == intent.id))).all()}
        for q in wanted:
            if q not in have:
                session.add(IntentQuestion(intent_id=intent.id, question_text=q, origin="ai"))
                n_questions += 1
        # 文件里删掉的问法要跟着删:它是"这个意图的问法集合"的唯一出处
        for text, row in have.items():
            if text not in wanted:
                await session.delete(row)
    return {"intents": n_intents, "questions_added": n_questions}


async def _non_data_faces(session, kb: KnowledgeBase) -> int:
    wanted = _load("non_data_faces.json")["faces"]
    have = {f.face_text: f for f in (await session.scalars(
        select(NonDataFace).where(NonDataFace.kb_id == kb.id))).all()}
    added = 0
    for text in wanted:
        if text not in have:
            session.add(NonDataFace(kb_id=kb.id, face_text=text, origin="human"))
            added += 1
    for text, row in have.items():
        if text not in wanted:
            await session.delete(row)
    return added


async def _build_index(session, kb: KnowledgeBase) -> dict:
    intents = (await session.scalars(
        select(SqlIntent).where(SqlIntent.kb_id == kb.id,
                                SqlIntent.status == "published"))).all()
    faces = 0
    for intent in intents:
        faces += await indexer.rebuild_intent_faces(session, intent)
    non_data = await indexer.rebuild_non_data_faces(session, kb.id)
    return {"intent_faces": faces, "non_data_faces": non_data}


async def main(rebuild_only: bool = False) -> None:
    async with SessionLocal() as session:
        kb = await _kb(session)
        print(f"知识库:{kb.name}  ({kb.id})")

        if not rebuild_only:
            ds = await _datasource(session, kb)
            print(f"数据源:{DATASOURCE_NAME} → {bizdb.demo_conn().masked()}(连接串已加密)")
            layer_counts = await _semantic_layer(session, ds)
            print(f"语义层:{layer_counts['tables']} 表 / {layer_counts['columns']} 列 / "
                  f"{layer_counts['relations']} 条 join 提示,"
                  f"其中 {layer_counts['described_columns']} 列盖上了评审过的描述")
            intent_counts = await _intents(session, kb, ds)
            print(f"意图:{intent_counts['intents']} 个已发布,"
                  f"新增 {intent_counts['questions_added']} 条相似问法")
            print(f"空路由负例面:新增 {await _non_data_faces(session, kb)} 条")
            await session.flush()

        print("建索引面(现算 embedding,这一步会真花钱)...")
        built = await _build_index(session, kb)
        await session.commit()

        size = await indexer.index_size(session, kb.id)
        print(f"索引:{size['intents']} 个已发布意图 / {size['faces']} 条面 "
              f"(摘要 {size['summary']} + 问法 {size['question']} + 空路由 {size['non_data']})")
        print(f"本次重建:{built['intent_faces']} 条意图面 + {built['non_data_faces']} 条负例面")
    print("\nS3 演示知识就绪。自检:uv run python -m scripts.smoke_s3_e2e --check")


if __name__ == "__main__":
    asyncio.run(main(rebuild_only="--rebuild-vectors" in sys.argv))
