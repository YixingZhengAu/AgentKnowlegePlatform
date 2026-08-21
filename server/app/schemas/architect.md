# server/app/schemas/architect.md

## 约定

- 列表接口统一返回 `ListResponse[T]`(`{items, total}`),后续加分页不破坏契约
- 出参类名后缀 `Out`,入参 `In` / `Create` / `Patch`
- 从 ORM 对象来的模型继承 `ORMModel`(`from_attributes=True`),用 `model_validate(row)`
- **拼接类出参**(带 ORM 上不存在的字段,如 `AgentDetailOut.bindings`)不能用 `model_validate(orm)`,
  要显式构造:见 `app/api/agents.py:get_agent`
- 改这里的字段名 = 改契约:必须跑 `make types`,前端编译会立刻报错(这是有意的)
