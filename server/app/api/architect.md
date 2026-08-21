# server/app/api/architect.md

## 约定

- 路径参数一律用 `uuid.UUID` 类型,不要用 `str` ——
  否则非法 uuid 会一路走到 DB,报成 `db_error 503` 而不是 `validation_error 422`
- 找不到资源:`raise NotFoundError(...)`(app/core/errors.py),不要手写 HTTPException
- 需要 DB:形参加 `session: SessionDep`;需要当前用户:`user: CurrentUser`
- 列表排序显式写出来(前端不做二次排序)

## 现有接口的数据来源

- `/healthz`:`SELECT 1` 探活,DB 不通返回 503 + `status="unhealthy"`,**进程不崩**
- `/api/agents/{id}`:agents + agent_kb_bindings JOIN knowledge_bases,按 priority 升序
  (priority 越小越优先,seed 里精准 QA=10 最优先)

## 待加(后续 Step)

- Step 5:`POST /api/agents/{id}/chat`(SSE)、`GET /api/traces/{message_id}`
- Step 7:jobs 提交/查询;Step 8:staging 审核与发布
