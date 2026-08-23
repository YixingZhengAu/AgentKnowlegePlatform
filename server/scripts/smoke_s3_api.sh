#!/usr/bin/env bash
# S3 后端全链路冒烟(HTTP 层):数据源 → Schema 治理 → 意图 → 模板 Run → 发布/下线 → 索引
#
# 为什么要有这个脚本:这一层有 21 条路由、29 个操作,其中一半的价值在**错误路径**
# (没确认只读的数据源不许连、没 SQL 的意图不许发布、闸外的 SQL 必须被拒)。
# 手打 curl 试一遍要半小时且下次还得重来,固化成脚本后回归零成本。
#
# ★ 这个脚本是**不留痕的**:建出来的临时数据源与草稿意图都会删掉,下线过的意图会重新发布,
#   相似问法与负例面按原样存回。跑完 `make smoke-s3` 的评测集分数必须一个字不变 ——
#   否则它就成了会破坏演示数据的脚本,没人敢跑。
#
# 默认**不调 LLM**(0 成本)。加 --with-ai 才跑那四个花钱的接口(描述/意图/模板/相似问法)。
#
# 前置:make db(两个库都起着)、make seed && make seed-s3(演示知识在库里)、make api
# 跑法:cd server && ./scripts/smoke_s3_api.sh [http://localhost:8000] [--with-ai]
set -euo pipefail

API="http://localhost:8000"
WITH_AI=0
for arg in "$@"; do
  case "$arg" in
    --with-ai) WITH_AI=1 ;;
    http*) API="$arg" ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✅\033[0m %s\n' "$*"; }
skip() { printf '  \033[33m⏭\033[0m  %s\n' "$*"; }
die()  { printf '  \033[31m❌ %s\033[0m\n' "$*" >&2; exit 1; }

expect() {  # $1=期望码 $2=实际码 $3=说明 $4=响应体
  [[ "$2" == "$1" ]] || die "$3:期望 HTTP $1,实得 $2 —— $(echo "$4" | head -c 400)"
}
jqr() { echo "$1" | jq -r "$2"; }
# 发一个请求,把 body 放进 $body、状态码放进 $code
call() {
  local method="$1" path="$2" data="${3:-}"
  local resp
  if [[ -n "$data" ]]; then
    resp=$(curl -sS -w '\n%{http_code}' -X "$method" -H 'content-type: application/json' \
           -d "$data" "$API$path")
  else
    resp=$(curl -sS -w '\n%{http_code}' -X "$method" "$API$path")
  fi
  code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
}

command -v jq >/dev/null || die "需要 jq(brew install jq)"
BIZ_URL=$(grep -E '^BIZ_DATABASE_URL=' ../.env | head -1 | cut -d= -f2-)
[[ -n "$BIZ_URL" ]] || die "../.env 里没有 BIZ_DATABASE_URL"
# mysql+pymysql://user:pass@host:port/db
BIZ_USER=$(sed -E 's|.*//([^:]+):.*|\1|' <<<"$BIZ_URL")
BIZ_PASS=$(sed -E 's|.*//[^:]+:([^@]*)@.*|\1|' <<<"$BIZ_URL")
BIZ_HOST=$(sed -E 's|.*@([^:/]+).*|\1|' <<<"$BIZ_URL")
BIZ_PORT=$(sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|' <<<"$BIZ_URL")
BIZ_DB=$(sed -E 's|.*/([^/?]+)$|\1|' <<<"$BIZ_URL")
CONN="{\"host\":\"$BIZ_HOST\",\"port\":$BIZ_PORT,\"database\":\"$BIZ_DB\",\"user\":\"$BIZ_USER\",\"password\":\"$BIZ_PASS\"}"

step "0 健康检查与前置"
health=$(curl -sS "$API/healthz")
[[ "$(jqr "$health" .database)" == "ok" ]] || die "数据库不通:$health"
ok "后端在线,DB ok,embedding_dim=$(jqr "$health" .embedding_dim)"
types=$(curl -sS "$API/api/jobs/types")
for t in t2s_sync_schema t2s_describe t2s_intents; do
  echo "$types" | jq -e --arg t "$t" 'index($t)' >/dev/null || die "job 类型 $t 没注册:$types"
done
ok "三个 Job 类型已注册"

step "1 数据源列表(GET /datasources)—— 顺手断言口令没漏出去"
call GET /api/text2sql/datasources
expect 200 "$code" "列数据源" "$body"
[[ "$(jqr "$body" .total)" -ge 1 ]] || die "库里没有数据源,先跑 make seed-s3"
DS=$(jqr "$body" '.items[0].id')
grep -qi 'password' <<<"$body" && die "★ 出参里出现了 password 字段:$body"
[[ "$(jqr "$body" '.items[0].database')" == "$BIZ_DB" ]] || die "库名不对:$body"
ok "数据源 $(jqr "$body" '.items[0].name') / $(jqr "$body" '.items[0].tables') 张表 / \
$(jqr "$body" '.items[0].published_intents') 个已发布意图,响应无 password 字段"

step "2 测连(POST /datasources/test,未保存的表单)"
call POST /api/text2sql/datasources/test "$CONN"
expect 200 "$code" "测连" "$body"
[[ "$(jqr "$body" .ok)" == "true" ]] || die "测连失败:$body"
# 演示库的口令与用户名同字面(biz_reader),所以断言的是"user:pass@"这个泄漏形态,
# 不是"body 里出现过这个词" —— 后者会被 target 里的用户名假报警
grep -q "$BIZ_USER:$BIZ_PASS" <<<"$body" && die "★ 测连结果里回显了口令:$body"
ok "ok=true version=$(jqr "$body" .server_version) target=$(jqr "$body" .target)"

step "3 错误路径:连不上的数据源(端口写错)"
call POST /api/text2sql/datasources/test "$(jq -c '.port=13307' <<<"$CONN")"
expect 200 "$code" "连不上的测连" "$body"
[[ "$(jqr "$body" .ok)" == "false" && "$(jqr "$body" .error)" != "null" ]] \
  || die "连不上应该是 ok=false + error,而不是异常:$body"
ok "ok=false error=$(jqr "$body" .error | head -c 80)(连不上是业务结果,不是 5xx)"

step "4 建一个临时数据源(POST /datasources,故意不确认只读)"
call POST /api/text2sql/datasources \
  "{\"name\":\"smoke-temp\",\"conn\":$CONN,\"readonly_confirmed\":false}"
expect 201 "$code" "建数据源" "$body"
TMP=$(jqr "$body" .id)
grep -q "$BIZ_USER:$BIZ_PASS" <<<"$body" && die "★ 建出来的响应里有口令:$body"
ok "临时数据源 $TMP,响应不含口令"

step "5 错误路径:同名再建一次 → 409"
call POST /api/text2sql/datasources \
  "{\"name\":\"smoke-temp\",\"conn\":$CONN,\"readonly_confirmed\":false}"
expect 409 "$code" "同名数据源" "$body"
[[ "$(jqr "$body" .error.code)" == "datasource_name_taken" ]] || die "错误码不对:$body"
ok "409 datasource_name_taken"

step "6 ★ 错误路径:没确认只读的数据源不许同步 → 409"
call POST "/api/text2sql/datasources/$TMP/sync"
expect 409 "$code" "未确认只读就同步" "$body"
[[ "$(jqr "$body" .error.code)" == "datasource_not_readonly" ]] || die "错误码不对:$body"
ok "409 datasource_not_readonly(readonly 是拒,不是提示)"

step "7 确认只读后测连(PATCH + POST /{id}/test)"
call PATCH "/api/text2sql/datasources/$TMP" '{"readonly_confirmed":true}'
expect 200 "$code" "改数据源" "$body"
[[ "$(jqr "$body" .readonly_confirmed)" == "true" ]] || die "没改上:$body"
call POST "/api/text2sql/datasources/$TMP/test"
expect 200 "$code" "已存数据源测连" "$body"
[[ "$(jqr "$body" .ok)" == "true" ]] || die "测连失败:$body"
ok "readonly_confirmed=true,测连 ok(明文口令从密文里解出来用了,但没出接口)"

step "8 删掉临时数据源(DELETE)+ 404 复验"
call DELETE "/api/text2sql/datasources/$TMP"
expect 204 "$code" "删数据源" "$body"
call GET "/api/text2sql/datasources/$TMP"
expect 404 "$code" "删完再取" "$body"
ok "204 + 404(脚本不留痕)"

step "9 错误路径:挂着意图的数据源不许删 → 409"
call DELETE "/api/text2sql/datasources/$DS"
expect 409 "$code" "删有意图的数据源" "$body"
[[ "$(jqr "$body" .error.code)" == "datasource_has_intents" ]] || die "错误码不对:$body"
ok "409 datasource_has_intents"

step "10 Schema 治理页的数据(GET /datasources/{id}/schema)"
call GET "/api/text2sql/datasources/$DS/schema"
expect 200 "$code" "取 schema" "$body"
schema="$body"
[[ "$(jqr "$schema" '.tables | length')" == "7" ]] || die "不是 7 张表:$(jqr "$schema" '.tables|length')"
[[ "$(jqr "$schema" '.relations | length')" -ge 6 ]] || die "join 提示少于 6 条"
enum=$(jqr "$schema" '[.tables[]|select(.table_name=="orders")|.columns[]|select(.column_name=="status")][0]')
[[ "$(echo "$enum" | jq -r '.is_enum_like')" == "true" ]] || die "orders.status 没被识别成枚举"
[[ "$(echo "$enum" | jq -r '.enum_values | length')" -ge 4 ]] || die "枚举取值不全:$enum"
[[ "$(echo "$enum" | jq -r '.enum_values[0].meaning')" != "null" ]] || die "枚举缺业务含义(审描述要它)"
[[ "$(jqr "$schema" '[.tables[].columns[]|select((.sample_values|length)>0)]|length')" -ge 40 ]] \
  || die "采样值太少 —— 审描述的人就没有依据了"
ok "7 张表 / $(jqr "$schema" '.relations|length') 条 join / orders.status 枚举带业务含义 / 采样值就位"

step "11 按表保存(PUT /tables/{id}):enabled 与列的 is_sensitive 各来回一趟"
TM=$(jqr "$schema" '[.tables[]|select(.table_name=="customers")][0].id')
COL=$(jqr "$schema" '[.tables[]|select(.table_name=="customers")|.columns[]|select(.column_name=="name")][0]')
COL_ID=$(echo "$COL" | jq -r .id); COL_SENS=$(echo "$COL" | jq -r .is_sensitive)
call PUT "/api/text2sql/tables/$TM" \
  "{\"enabled\":false,\"columns\":[{\"id\":\"$COL_ID\",\"is_sensitive\":true}]}"
expect 200 "$code" "存表" "$body"
[[ "$(jqr "$body" .enabled)" == "false" ]] || die "表开关没写上:$body"
[[ "$(jqr "$body" '[.columns[]|select(.id=="'"$COL_ID"'")][0].is_sensitive')" == "true" ]] \
  || die "列开关没写上"
call PUT "/api/text2sql/tables/$TM" \
  "{\"enabled\":true,\"columns\":[{\"id\":\"$COL_ID\",\"is_sensitive\":$COL_SENS}]}"
expect 200 "$code" "还原表" "$body"
[[ "$(jqr "$body" .enabled)" == "true" ]] || die "没还原:$body"
ok "写进去读得到,原样还原(治理开关同时管住模板生成与执行闸白名单)"

step "12 错误路径:别的表的列不许从这里改 → 409"
OTHER_COL=$(jqr "$schema" '[.tables[]|select(.table_name=="orders")|.columns[0]][0].id')
call PUT "/api/text2sql/tables/$TM" \
  "{\"columns\":[{\"id\":\"$OTHER_COL\",\"description\":\"nope\"}]}"
expect 409 "$code" "跨表改列" "$body"
[[ "$(jqr "$body" .error.code)" == "column_not_in_table" ]] || die "错误码不对:$body"
ok "409 column_not_in_table(一次「保存 customers」不能悄悄改掉 orders)"

step "13 同步 schema(POST /datasources/{id}/sync,零 LLM)"
call POST "/api/text2sql/datasources/$DS/sync"
expect 200 "$code" "派发同步 Job" "$body"
JOB=$(jqr "$body" .job_id)
for ((i=0; i<60; i+=2)); do
  job=$(curl -sS "$API/api/jobs/$JOB"); st=$(jqr "$job" .status)
  [[ "$st" == "queued" || "$st" == "running" ]] || break
  sleep 2
done
[[ "$st" == "published" ]] || die "同步 Job 终态不是 published:$(echo "$job" | head -c 300)"
ok "Job $st,步骤:$(jqr "$job" '[.step_logs[]?.message // empty] | join(" | ")' | head -c 200)"

step "14 意图列表(GET /intents)"
call GET "/api/text2sql/intents?status=published"
expect 200 "$code" "列意图" "$body"
N_INTENTS=$(jqr "$body" .total)
[[ "$N_INTENTS" -ge 7 ]] || die "已发布意图少于 7 个,先跑 make seed-s3"
[[ "$(jqr "$body" '[.items[]|select(.face_count==0)]|length')" == "0" ]] \
  || die "有已发布意图没有索引面(半残状态):$body"
IT=$(jqr "$body" '.items[0].id'); IT_CODE=$(jqr "$body" '.items[0].code')
ok "$N_INTENTS 个已发布意图,每个都有索引面;第一个 = $IT_CODE"

step "15 意图详情(GET /intents/{id}):三区参数 + 发布前置"
call GET "/api/text2sql/intents/$IT"
expect 200 "$code" "意图详情" "$body"
[[ "$(jqr "$body" '.publish_blockers | length')" == "0" ]] || die "已发布意图却有 blockers:$body"
[[ "$(jqr "$body" '.params.outputs | length')" -ge 1 ]] || die "参数区没有输出列:$body"
[[ "$(jqr "$body" '[.params.filters[]|select(.hint=="")]|length')" == "0" ]] \
  || die "有 filter 没写 hint —— 改写模型会没有取值说明书"
[[ "$(jqr "$body" '.questions | length')" -ge 1 ]] || die "没有相似问法:$body"
ok "filters=$(jqr "$body" '.params.filters|length') outputs=$(jqr "$body" '.params.outputs|length') \
groupbys=$(jqr "$body" '.params.groupbys|length') questions=$(jqr "$body" '.questions|length'),hint 全非空"

step "16 错误路径:不存在的意图 → 404"
call GET "/api/text2sql/intents/00000000-0000-0000-0000-000000000000"
expect 404 "$code" "取不存在的意图" "$body"
ok "404"

step "17 手工新建一个草稿意图(POST /intents)"
call POST /api/text2sql/intents \
  '{"intent_type":"query","one_liner":"Query: smoke draft","brief":"Temporary intent created by smoke_s3_api.sh; it is deleted at the end of the run.","tables":["orders"]}'
expect 201 "$code" "建意图" "$body"
DRAFT=$(jqr "$body" .id)
[[ "$(jqr "$body" .status)" == "draft" ]] || die "新建的不是 draft:$body"
[[ "$(jqr "$body" .human_edited)" == "true" ]] || die "手工建的没标 human_edited"
ok "草稿 $(jqr "$body" .code)(采纳 ≠ 发布:手工新建也只是 draft)"

step "18 ★ 错误路径:没有 SQL 的意图不许发布 → 409(理由要能直接显示给用户)"
call POST "/api/text2sql/intents/$DRAFT/publish"
expect 409 "$code" "发布无 SQL 的意图" "$body"
[[ "$(jqr "$body" .error.code)" == "sql_intent_not_publishable" ]] || die "错误码不对:$body"
[[ "$(jqr "$body" '.error.detail.blockers | length')" -ge 2 ]] || die "blockers 没带回来:$body"
ok "409 sql_intent_not_publishable:$(jqr "$body" '.error.detail.blockers | join(" ")' | head -c 120)"

step "19 错误路径:没有 SQL 也谈不上解析参数区 → 409"
call POST "/api/text2sql/intents/$DRAFT/parse-params"
expect 409 "$code" "解析空 SQL" "$body"
[[ "$(jqr "$body" .error.code)" == "sql_intent_no_sql" ]] || die "错误码不对:$body"
ok "409 sql_intent_no_sql"

step "20 模板 Run(POST /intents/{id}/run):走的就是运行时那道执行闸"
call POST "/api/text2sql/intents/$DRAFT/run" \
  '{"sql":"SELECT o.order_no AS order_number, o.total_amount AS total FROM orders o ORDER BY o.order_date DESC LIMIT 3"}'
expect 200 "$code" "Run" "$body"
[[ "$(jqr "$body" .ok)" == "true" ]] || die "Run 失败:$body"
[[ "$(jqr "$body" .rowcount)" == "3" ]] || die "行数不对:$body"
[[ "$(jqr "$body" '.rows | length')" == "3" ]] || die "没回带结果行(人要靠它判断数对不对)"
ok "3 行 / 列 $(jqr "$body" '.cols|join(", ")') / sql_executed 带 LIMIT"

step "21 ★ 错误路径:LIMIT 超上限会被闸压回去"
call POST "/api/text2sql/intents/$DRAFT/run" \
  '{"sql":"SELECT o.order_no AS n FROM orders o LIMIT 99999"}'
expect 200 "$code" "超限 LIMIT" "$body"
[[ "$(jqr "$body" .ok)" == "true" ]] || die "应该被压回上限而不是报错:$body"
grep -qE 'LIMIT (500|[0-9]{1,3})$' <<<"$(jqr "$body" .sql_executed)" \
  || die "LIMIT 没被压回:$(jqr "$body" .sql_executed)"
ok "sql_executed = …$(jqr "$body" .sql_executed | tail -c 20)(强制 LIMIT 生效)"

step "22 ★ 错误路径:白名单外的表 / 多条语句 → ok=false"
call POST "/api/text2sql/intents/$DRAFT/run" \
  '{"sql":"SELECT t.table_name AS n FROM information_schema.tables t LIMIT 1"}'
expect 200 "$code" "闸外的表" "$body"
[[ "$(jqr "$body" .ok)" == "false" ]] || die "语义层白名单外的表居然放行了:$body"
grep -q "not in semantic layer whitelist" <<<"$(jqr "$body" .error)" || die "报错不对:$body"
ok "白名单:$(jqr "$body" .error)"
call POST "/api/text2sql/intents/$DRAFT/run" '{"sql":"SELECT 1 AS a; SELECT 2 AS b"}'
expect 200 "$code" "两条语句" "$body"
[[ "$(jqr "$body" .ok)" == "false" ]] || die "多条语句居然放行了:$body"
ok "单条 SELECT:$(jqr "$body" .error)"

step "23 删掉草稿意图(DELETE /intents/{id})"
call DELETE "/api/text2sql/intents/$DRAFT"
expect 204 "$code" "删草稿" "$body"
ok "204(脚本不留痕)"

step "24 索引统计(GET /index-stats)"
call GET /api/text2sql/index-stats
expect 200 "$code" "索引统计" "$body"
F_SUM=$(jqr "$body" .summary); F_Q=$(jqr "$body" .question); F_ND=$(jqr "$body" .non_data)
TOTAL0=$(jqr "$body" .total)
[[ "$F_ND" -ge 1 ]] || die "★ 没有空路由负例面 —— 空路由被关掉了,非问数问题会撞进最近的模板"
ok "摘要 $F_SUM / 问法 $F_Q / 空路由 $F_ND = 共 $TOTAL0 条面"

step "25 下线 → 重新发布(索引面必须回到原样)"
call POST "/api/text2sql/intents/$IT/disable"
expect 200 "$code" "下线" "$body"
[[ "$(jqr "$body" .status)" == "disabled" ]] || die "没下线:$body"
call GET /api/text2sql/index-stats
[[ "$(jqr "$body" .total)" -lt "$TOTAL0" ]] || die "下线后索引面没减少 —— 它还在被检索到"
call POST "/api/text2sql/intents/$IT/publish"
expect 200 "$code" "重新发布" "$body"
ok "重新发布:意图面 $(jqr "$body" .faces) + 空路由面 $(jqr "$body" .non_data_faces)"
call GET /api/text2sql/index-stats
[[ "$(jqr "$body" .total)" == "$TOTAL0" ]] \
  || die "索引面没回到 $TOTAL0:$(jqr "$body" .total)"
ok "索引面回到 $TOTAL0(全删重建,不做增量 diff)"

step "26 相似问法整组存回(PUT …/questions):保存即重建索引面"
call GET "/api/text2sql/intents/$IT/questions"
expect 200 "$code" "列问法" "$body"
QS=$(jqr "$body" '[.items[].question_text]')
N_Q=$(echo "$QS" | jq 'length')
call PUT "/api/text2sql/intents/$IT/questions" "{\"questions\":$QS}"
expect 200 "$code" "存问法" "$body"
[[ "$(jqr "$body" '.questions | length')" == "$N_Q" ]] || die "问法数变了:$body"
[[ "$(jqr "$body" .faces)" == "$((N_Q + 1))" ]] \
  || die "面数应为 问法数+摘要=$((N_Q + 1)),实得 $(jqr "$body" .faces)"
ok "$N_Q 条问法 → $(jqr "$body" .faces) 条面(摘要 + 每条问法各一行)"

step "27 空路由负例面整组存回(PUT /non-data-faces)"
call GET /api/text2sql/non-data-faces
expect 200 "$code" "列负例面" "$body"
FACES=$(jqr "$body" '[.items[].face_text]')
call PUT /api/text2sql/non-data-faces "{\"faces\":$FACES}"
expect 200 "$code" "存负例面" "$body"
[[ "$(jqr "$body" .indexed)" == "$F_ND" ]] || die "负例面数变了:$(jqr "$body" .indexed) != $F_ND"
ok "$(jqr "$body" .indexed) 条负例面原样存回"

call GET /api/text2sql/index-stats
[[ "$(jqr "$body" .total)" == "$TOTAL0" ]] || die "收尾时索引面不是 $TOTAL0:$(jqr "$body" .total)"
ok "收尾复核:索引面仍是 $TOTAL0 条 —— 评测集分数不会因为跑了这个脚本而变"

if [[ "$WITH_AI" == "1" ]]; then
  step "28 (--with-ai)单表描述生成(POST /tables/{id}/describe,同步、一次 gpt-5)"
  call POST "/api/text2sql/tables/$TM/describe" '{"mode":"rewrite"}'
  expect 200 "$code" "生成描述" "$body"
  [[ -n "$(jqr "$body" .description)" ]] || die "没生成表描述:$body"
  [[ "$(jqr "$body" '[.columns[]|select(.description=="")]|length')" == "0" ]] \
    || die "有列没描述:$body"
  ok "整表建议:$(jqr "$body" '.columns|length') 列全有描述(建议未落库,人确认后再存)"

  step "29 (--with-ai)相似问法生成(POST …/questions/generate)"
  call POST "/api/text2sql/intents/$IT/questions/generate?n=4"
  expect 200 "$code" "生成问法" "$body"
  [[ "$(jqr "$body" '.questions | length')" -ge 1 ]] || die "一条都没生成:$body"
  ok "留下 $(jqr "$body" '.questions|length') 条,丢弃 $(jqr "$body" '.dropped|length') 条\
$(jqr "$body" 'if (.dropped|length)>0 then "(" + .dropped[0].reason + ")" else "" end')"

  step "30 (--with-ai)模板生成(POST /intents/{id}/template,B4+B5 全链路)"
  call POST /api/text2sql/intents \
    '{"intent_type":"stats","one_liner":"Stats: monthly revenue by state","brief":"Monthly total order revenue broken down by customer state, over a date range, excluding cancelled orders. Users vary the date range and the states included.","tables":["orders","customers"]}'
  expect 201 "$code" "建意图" "$body"
  AI_DRAFT=$(jqr "$body" .id)
  call POST "/api/text2sql/intents/$AI_DRAFT/template"
  expect 200 "$code" "生成模板" "$body"
  [[ "$(jqr "$body" .trial_rowcount)" -gt 0 ]] || die "试执行 0 行 —— 模板生成的通过条件之一没满足"
  [[ "$(jqr "$body" '.intent.params.filters | length')" -ge 1 ]] || die "参数区没解析出 filter"
  ok "修复 $(jqr "$body" .repair_rounds) 轮 / 预填 $(jqr "$body" .prefill_rounds) 轮 / \
试执行 $(jqr "$body" .trial_rowcount) 行 / filters=$(jqr "$body" '.intent.params.filters|length')"
  call POST "/api/text2sql/intents/$AI_DRAFT/parse-params"
  expect 200 "$code" "重解析参数区" "$body"
  ok "按当前 SQL 重解析:保住了 $(jqr "$body" .kept_annotations) 条人工/AI 注释"
  call DELETE "/api/text2sql/intents/$AI_DRAFT"
  expect 204 "$code" "删掉 AI 草稿" "$body"
  ok "204(不留痕)"
else
  skip "28–30 花钱的四个接口(描述/问法/模板生成)—— 加 --with-ai 才跑"
fi

printf '\n\033[32m全部通过\033[0m(%s)\n' "$API"
