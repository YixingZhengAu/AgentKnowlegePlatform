#!/usr/bin/env bash
# S2 文档 RAG 冒烟(HTTP 层):切片管理 / 禁用启用 / 引用回显 / 检索调试台
#
# 为什么要有这个脚本:S2-4 那几条纪律**错了都不报错**,只是安静地做错事 ——
#   ① 两条召回 SQL 各有一份 `status='active'`,漏一条就是"禁用了还能被搜到";
#   ② 禁用要清向量、启用要用**和发布时一样的拼法**重算,差一个换行就换了一个向量;
#   ③ 被引用过的行不许物理删,删了历史会话的引用就悬空。
# 这三条只有打真后端才验得出来,单测碰不到(tests/ 全部离线)。
#
# ★ 这个脚本**默认不留痕**:禁用过的切片会启用回来,不建也不删任何文档。
#   跑完 `/search` 的结果必须与跑之前一个字不变 —— 否则它就成了会破坏演示数据的脚本,没人敢跑。
#
# 默认几乎零成本:只有"启用"那一步会调一次 Embedding(那正是要验的东西)。
# 加 --with-rerun 才跑分册 4 §6 的第四条(单文档重跑),它**会改演示数据**:
#   重新解析 + 重新描述(花钱),旧切片被退休,切片 id 全换一批。演示前不要跑。
#
# 前置:make db、make api,且**至少有一份已发布的文档**(上传见 /ingest/document)
# 跑法:cd server && ./scripts/smoke_s2_api.sh [http://localhost:8000] [--with-rerun]
set -euo pipefail

API="http://localhost:8000"
WITH_RERUN=0
for arg in "$@"; do
  case "$arg" in
    --with-rerun) WITH_RERUN=1 ;;
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
# 允许透传 --arg 等参数:jqr "$body" --arg d "$DOC" '.items[]|select(.id==$d)'
jqr() { local b="$1"; shift; echo "$b" | jq -r "$@"; }
call() {  # 发一个请求,body 进 $body、状态码进 $code
  local method="$1" path="$2" data="${3:-}" resp
  if [[ -n "$data" ]]; then
    resp=$(curl -sS -w '\n%{http_code}' -X "$method" -H 'content-type: application/json' \
           -d "$data" "$API$path")
  else
    resp=$(curl -sS -w '\n%{http_code}' -X "$method" "$API$path")
  fi
  code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
}
# 出错也要把禁用过的切片放回去 —— 半路失败留下一条搜不到的切片,比脚本失败本身更糟
DISABLED=""
restore() {
  [[ -z "$DISABLED" ]] && return 0
  curl -sS -o /dev/null -X POST "$API/api/document/chunks/$DISABLED/enable" || true
  printf '  \033[33m↩\033[0m  已把 %s 启用回去\n' "${DISABLED:0:8}"
}
trap restore EXIT

command -v jq >/dev/null || die "需要 jq(brew install jq)"

# ── 0 前置 ────────────────────────────────────────────────────────────────────
step "0 健康检查与语料就位"
health=$(curl -sS "$API/healthz")
[[ "$(jqr "$health" .database)" == "ok" ]] || die "数据库不通:$health"
ok "后端在线,DB ok,embedding_dim=$(jqr "$health" .embedding_dim)"

call GET /api/document/documents
expect 200 "$code" "文档列表" "$body"
DOC=$(jqr "$body" '[.items[] | select(.stage=="published" and .chunk_count>0)][0].id')
[[ "$DOC" != "null" ]] || die "没有已发布且有切片的文档 —— 先上传一份 PDF 走完审核发布"
DOC_NAME=$(jqr "$body" --arg d "$DOC" '.items[] | select(.id==$d) | .name')
DOC_CHUNKS=$(jqr "$body" --arg d "$DOC" '.items[] | select(.id==$d) | .chunk_count')
ok "拿 $DOC_NAME 当靶子($DOC_CHUNKS 条在用的切片)"

# ── 1 切片管理页的数据面 ──────────────────────────────────────────────────────
step "1 切片列表(GET /documents/{id}/chunks)"
call GET "/api/document/documents/$DOC/chunks"
expect 200 "$code" "切片列表" "$body"
LIVE=$(jqr "$body" '.items | length')
[[ "$LIVE" == "$DOC_CHUNKS" ]] || die "列表 $LIVE 条,文档列表说 $DOC_CHUNKS 条 —— 两处计数口径不一致"
jqr "$body" '.items[] | select(.retired)' | grep -q . && die "默认列表里混进了退休行"
NO_VEC=$(jqr "$body" '[.items[] | select(.status=="active" and (.embedded|not))] | length')
[[ "$NO_VEC" == "0" ]] || die "有 $NO_VEC 条 active 切片没有向量 —— 它们永远召不回"
SEQS=$(jqr "$body" '[.items[].seq] | @csv')
GAPS=$(jqr "$body" '[.items[].seq] | (max - min + 1) - length')
ok "$LIVE 条全部 active 且有向量;seq=$SEQS(空洞 $GAPS 个 —— 合并/驳回留下的,不重排)"

step "1b 退休行只在 include_retired 时出现"
call GET "/api/document/documents/$DOC/chunks?include_retired=true"
expect 200 "$code" "含退休行" "$body"
RETIRED=$(jqr "$body" '[.items[] | select(.retired)] | length')
RETIRED_ID=$(jqr "$body" '[.items[] | select(.retired)][0].id')
if [[ "$RETIRED" -gt 0 ]]; then
  # 退休行必须已经清了向量 —— 否则它还占着 HNSW 索引
  jqr "$body" '[.items[] | select(.retired and .embedded)] | length' | grep -qx 0 \
    || die "退休行还留着向量"
  ok "$RETIRED 条退休行(全部无向量),默认列表看不到它们"
else
  skip "这份文档还没有退休行(没重新发布过)"
fi

# ── 2 引用回显 ────────────────────────────────────────────────────────────────
step "2 引用回显(GET /chunks/{id})—— 点开 [n] 走的就是它"
FIRST=$(curl -sS "$API/api/document/documents/$DOC/chunks" | jq -r '.items[0].id')
call GET "/api/document/chunks/$FIRST"
expect 200 "$code" "切片详情" "$body"
[[ "$(jqr "$body" '.content | length')" -gt 0 ]] || die "详情没有正文"
[[ "$(jqr "$body" .document_name)" == "$DOC_NAME" ]] || die "详情里的文档名对不上"
ok "全文 $(jqr "$body" '.content|length') 字 / page $(jqr "$body" '.page_idx + 1') / \
figures $(jqr "$body" '.figures|length') / retired=$(jqr "$body" .retired)"

call GET "/api/document/chunks/00000000-0000-0000-0000-000000000000"
expect 404 "$code" "不存在的切片" "$body"
[[ "$(jqr "$body" .error.code)" == "chunk_not_found" ]] || die "错误码不是 chunk_not_found"
ok "不存在的 id → 404 chunk_not_found(前端据此显示"已不在库里")"

# ── 3 检索调试台 ──────────────────────────────────────────────────────────────
step "3 检索调试台(GET /search)"
# 探针取自语料自身:标题末段一定逐字出现在正文里(chunker 把标题留在该节第一位),
# 于是关键词腿必中,向量腿也必中 —— 不依赖任何硬编码的业务词
PROBE=$(curl -sS "$API/api/document/documents/$DOC/chunks" \
  | jq -r '[.items[] | select(.heading_path != null)] | max_by(.token_count) | .heading_path'\
  | awk -F' > ' '{print $NF}' | sed 's/^[0-9.]* *//')
[[ -n "$PROBE" ]] || die "没能从语料里凑出探针词"
call GET "/api/document/search?q=$(jq -rn --arg q "$PROBE" '$q|@uri')"
expect 200 "$code" "检索" "$body"
[[ "$(jqr "$body" .empty)" == "false" ]] || die "探针"$PROBE"一条都没召回"
V0=$(jqr "$body" .recall.vector); F0=$(jqr "$body" .recall.fts)
ok "探针"$PROBE":向量腿 $V0 / 关键词腿 $F0 / 融合 $(jqr "$body" .recall.fused) / \
重排=$(jqr "$body" .reranked) / guard=$(jqr "$body" .guard_fallback)"

# 挑一条**两条腿都召回了**的当靶子,这样禁用后两条腿各掉 1,一次验完两处过滤
TARGET=$(jqr "$body" '[.hits[] | select(.rank_vector != null and .rank_fts != null)][0]')
[[ "$TARGET" != "null" ]] || die "top-5 里没有一条两条腿都命中的 —— 换个探针再跑"
CID=$(jqr "$TARGET" .chunk_id); SCORE0=$(jqr "$TARGET" .score)
ok "靶子 chunk#$(jqr "$TARGET" .seq):向量第 $(jqr "$TARGET" .rank_vector) / \
关键词第 $(jqr "$TARGET" .rank_fts) / 重排分 $SCORE0"

step "3b guard:语料外的问题必须触发"
call GET "/api/document/search?q=zzq%20quantum%20ferret%20submarine%20tuesday"
expect 200 "$code" "语料外检索" "$body"
[[ "$(jqr "$body" .guard_fallback)" == "true" ]] \
  || die "整题失灵没被 guard 接住(top=$(jqr "$body" '.hits[0].score')) —— 阈值 DOC_RAG_RERANK_GUARD 是不是被调松了"
ok "guard 触发,列表退回 RRF 名次(top 分 $(jqr "$body" '.hits[0].score'))"

# ── 4 断言一:禁用 → 两条腿都不再返回 ─────────────────────────────────────────
step "4 【断言 1】禁用 → 向量腿与关键词腿**同时**不再返回它"
call POST "/api/document/chunks/$CID/disable"
expect 200 "$code" "禁用" "$body"
DISABLED="$CID"
[[ "$(jqr "$body" .status)" == "disabled" ]] || die "状态没变成 disabled"
[[ "$(jqr "$body" .embedded)" == "false" ]] || die "禁用了却没清向量 —— HNSW 里留了条死数据"
ok "status=disabled,embedding 已清空"

call GET "/api/document/search?q=$(jq -rn --arg q "$PROBE" '$q|@uri')"
expect 200 "$code" "禁用后检索" "$body"
echo "$body" | jq -e --arg c "$CID" '[.hits[].chunk_id] | index($c)' >/dev/null \
  && die "🩸 禁用了还能被搜到 —— 两条召回 SQL 至少漏了一条 status='active'"
V1=$(jqr "$body" .recall.vector); F1=$(jqr "$body" .recall.fts)
[[ "$V1" -eq "$((V0 - 1))" ]] || die "向量腿没少一条($V0 → $V1)—— _search_vector 的过滤没生效"
[[ "$F1" -eq "$((F0 - 1))" ]] || die "关键词腿没少一条($F0 → $F1)—— _search_fts 的过滤没生效"
ok "结果里没有它;向量腿 ${V0}→${V1}、关键词腿 ${F0}→${F1},**两条各少一条**"

# ── 5 断言三:被引用过也不许物理删 ────────────────────────────────────────────
step "5 【断言 3】禁用不是删除 —— 历史会话的引用仍然点得开"
call GET "/api/document/chunks/$CID"
expect 200 "$code" "禁用后读详情" "$body"
[[ "$(jqr "$body" '.content | length')" -gt 0 ]] || die "正文没了"
ok '正式行还在,GET /chunks/{id} 照样返回全文 —— message_citations.ref_id 不会悬空'

step "5b 错误路径"
call POST "/api/document/chunks/$CID/disable"
expect 409 "$code" "重复禁用" "$body"
[[ "$(jqr "$body" .error.code)" == "chunk_already_disabled" ]] || die "错误码不对:$body"
ok "重复禁用 → 409 chunk_already_disabled"
if [[ "$RETIRED" -gt 0 ]]; then
  call POST "/api/document/chunks/$RETIRED_ID/enable"
  expect 409 "$code" "启用退休行" "$body"
  [[ "$(jqr "$body" .error.code)" == "chunk_retired" ]] || die "错误码不对:$body"
  ok "退休行不许启用 → 409 chunk_retired(它的正文已被新一版取代)"
else
  skip "没有退休行可试 chunk_retired"
fi

# ── 6 断言二:启用 → 向量重建且**与发布时同一个向量** ─────────────────────────
step "6 【断言 2】启用 → 重算向量,又能被召回"
call POST "/api/document/chunks/$CID/enable"
expect 200 "$code" "启用" "$body"
DISABLED=""
[[ "$(jqr "$body" .status)" == "active" ]] || die "状态没回到 active"
[[ "$(jqr "$body" .embedded)" == "true" ]] || die "向量没重建"
ok "status=active,embedding 已重建"

call GET "/api/document/search?q=$(jq -rn --arg q "$PROBE" '$q|@uri')"
expect 200 "$code" "启用后检索" "$body"
BACK=$(jqr "$body" --arg c "$CID" '[.hits[] | select(.chunk_id==$c)][0]')
[[ "$BACK" != "null" ]] || die "启用了却召不回来"
V2=$(jqr "$body" .recall.vector); F2=$(jqr "$body" .recall.fts)
[[ "$V2" -eq "$V0" && "$F2" -eq "$F0" ]] || die "两条腿没回到原样($V0/$F0 → $V2/$F2)"
SCORE1=$(jqr "$BACK" .score)
# 🩸 这一条比分册要求的更严:分数**必须与禁用前逐字相同**。
# 它钉住的是 `embed_input()` 只有一处 —— 发布与重新启用的拼法差一个换行,
# 算出来就是另一个向量,而那种漂移不报错,只会让召回行为悄悄变了。
[[ "$SCORE1" == "$SCORE0" ]] \
  || die "重排分变了($SCORE0 → $SCORE1)—— 启用时重算的向量和发布时的不是同一个,查 embed_input()"
ok "召回回来了,两条腿回到 ${V2}/${F2},**重排分 ${SCORE1} 与禁用前完全相同**(同一个向量)"

# ── 7 断言四(可选,会改演示数据)─────────────────────────────────────────────
if [[ "$WITH_RERUN" == "1" ]]; then
  step "7 【断言 4】单文档重跑:旧行退休而不是被删,新一批从 0 起"
  BEFORE=$(curl -sS "$API/api/document/documents/$DOC/chunks?include_retired=true" \
           | jq '[.items[] | select(.retired|not)] | length')
  call POST "/api/document/documents/$DOC/reingest"
  expect 201 "$code" "重跑" "$body"
  JOB=$(jqr "$body" .job_id)
  [[ "$(jqr "$body" .live_chunks)" -eq "$BEFORE" ]] || die "回执里的 live_chunks 与实际不符"
  ok "job=$JOB;重跑期间 $BEFORE 条旧切片仍然对外可召回"

  for _ in $(seq 1 40); do
    JS=$(jqr "$(curl -sS "$API/api/jobs/$JOB")" .status)
    [[ "$JS" == "review" || "$JS" == "failed" ]] && break
    sleep 6
  done
  [[ "$JS" == "review" ]] || die "重跑没到 review(status=$JS)"
  ok "五步跑完,停在人工关 —— 重跑**必须**重审,不然等于白跑"

  IDS=$(curl -sS "$API/api/staging?job_id=$JOB&page_size=200" | jq -c '[.items[].id]')
  call POST /api/staging/bulk "{\"ids\": $IDS, \"review_status\": \"approved\"}"
  expect 200 "$code" "批量通过" "$body"
  call POST "/api/jobs/$JOB/publish" '{}'
  expect 200 "$code" "发布" "$body"
  NEW=$(jqr "$body" .published)
  ok "发布 $NEW 条"

  call GET "/api/document/documents/$DOC/chunks?include_retired=true"
  expect 200 "$code" "重跑后列表" "$body"
  [[ "$(jqr "$body" '[.items[] | select(.retired|not)][0].seq')" == "0" ]] \
    || die "新一批的 seq 没从 0 起"
  R=$(jqr "$body" '[.items[] | select(.retired)] | length')
  ok "新一批 $NEW 条从 seq=0 起;$R 条被引用过的旧行退休(没被物理删)"

  if [[ "$R" -gt 0 ]]; then
    RID=$(jqr "$body" '[.items[] | select(.retired)][0].id')
    call GET "/api/document/chunks/$RID"
    expect 200 "$code" "读退休行" "$body"
    ok "退休行仍读得到 —— 老会话里那条引用点开还是原文"
  fi
  printf '  \033[33m⚠\033[0m  演示数据已变(切片 id 全换一批),这是 --with-rerun 的代价\n'
else
  skip "7 单文档重跑(分册 4 §6 第四条)—— 它会改演示数据,加 --with-rerun 才跑"
fi

printf '\n\033[32m[smoke_s2_api] 全链路通过 ✅\033[0m  document=%s target_chunk=%s\n' "$DOC_NAME" "${CID:0:8}"
printf '  分册 4 §6 四条断言:1 ✅ / 2 ✅ / 3 ✅ / 4 %s\n' \
  "$([[ "$WITH_RERUN" == "1" ]] && echo '✅' || echo '⏭ (--with-rerun)')"
