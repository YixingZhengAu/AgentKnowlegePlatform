#!/usr/bin/env bash
# S1 后端全链路冒烟(HTTP 层):上传 → 轮询解析完 → 读校对文本 → 写回 → 确认抽取
#                              → 轮询抽取完 → 列候选 → 采纳一条 + 不采纳一条 → 列正式 QA → 图片端点
#
# 为什么要有这个脚本(S1-plan §7.1 第 2 层):这条链路有 9 个来回、3 个人工衔接点,
# 手打 curl 试一遍要十几分钟且下次还得重来;固化成脚本后回归零成本(Step 8 直接重跑)。
#
# 前置:make db(库起着)、make api(后端在 8000)、MinerU 容器起着
#       (make mineru)
# 跑法:cd server && ./scripts/smoke_s1_api.sh [http://localhost:8000]
set -euo pipefail

API="${1:-http://localhost:8000}"
PDF="$(cd "$(dirname "$0")" && pwd)/fixtures/sample-paper-3p.pdf"
# 解析实测 ~20s、抽取(gpt-5 两段 + 36 条 gpt-5-mini)实测 ~5min,超时给足余量
PARSE_TIMEOUT=180
EXTRACT_TIMEOUT=900

step() { printf '\n\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✅\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m❌ %s\033[0m\n' "$*" >&2; exit 1; }

# 断言 HTTP 码:$1=期望码 $2=实际码 $3=说明 $4=响应体
expect() {
  [[ "$2" == "$1" ]] || die "$3:期望 HTTP $1,实得 $2 —— $(echo "$4" | head -c 300)"
}

jqr() { echo "$1" | jq -r "$2"; }

command -v jq >/dev/null || die "需要 jq(brew install jq)"
[[ -f "$PDF" ]] || die "测试 PDF 不在:$PDF"

step "0 健康检查与前置"
health=$(curl -sS "$API/healthz")
[[ "$(jqr "$health" .database)" == "ok" ]] || die "数据库不通:$health"
ok "后端在线,DB ok,embedding_dim=$(jqr "$health" .embedding_dim)"
types=$(curl -sS "$API/api/jobs/types")
for t in qa_parse qa_extract; do
  echo "$types" | jq -e --arg t "$t" 'index($t)' >/dev/null || die "job 类型 $t 没注册:$types"
done
ok "job 类型已注册:$(echo "$types" | jq -c .)"

step "1 上传 PDF(POST /api/exact-qa/documents)"
resp=$(curl -sS -w '\n%{http_code}' -F "file=@$PDF;type=application/pdf" "$API/api/exact-qa/documents")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 201 "$code" "上传" "$body"
DOC=$(jqr "$body" .document_id); PARSE_JOB=$(jqr "$body" .job_id)
ok "document=$DOC parse_job=$PARSE_JOB"

step "2 非 PDF 应被拒(边界:S1 只收 PDF)"
resp=$(curl -sS -w '\n%{http_code}' -F "file=@$PDF;type=text/plain" "$API/api/exact-qa/documents")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 409 "$code" "非 PDF 上传" "$body"
[[ "$(jqr "$body" .error.code)" == "unsupported_file_type" ]] || die "错误码不对:$body"
ok "409 unsupported_file_type"

step "3 轮询解析 Job 直到完成(上限 ${PARSE_TIMEOUT}s)"
for ((i=0; i<PARSE_TIMEOUT; i+=3)); do
  job=$(curl -sS "$API/api/jobs/$PARSE_JOB")
  st=$(jqr "$job" .status)
  [[ "$st" == "published" || "$st" == "failed" ]] && break
  printf '\r  %ss status=%s step=%s progress=%s' "$i" "$st" "$(jqr "$job" .current_step)" "$(jqr "$job" .progress)"
  sleep 3
done
printf '\n'
[[ "$st" == "published" ]] || die "解析失败:$(jqr "$job" '.error // .status')"
ok "解析完成:$(jqr "$job" '.step_logs[-1].message')"

doc=$(curl -sS "$API/api/exact-qa/documents/$DOC")
[[ "$(jqr "$doc" .parse_status)" == "parsed" ]] || die "文档状态应为 parsed:$doc"
[[ "$(jqr "$doc" .stage)" == "review_text" ]] || die "推导态应为 review_text:$(jqr "$doc" .stage)"
ok "文档 stage=review_text,页数=$(jqr "$doc" .parse_stats.page_count) 块=$(jqr "$doc" .parse_stats.block_count) 图=$(jqr "$doc" .parse_stats.image_count)"

step "4 读校对文本(图片 URL 应已改写成文件服务)"
rt=$(curl -sS "$API/api/exact-qa/documents/$DOC/review-text")
[[ "$(jqr "$rt" .source)" == "paged.md" ]] || die "首次应读 paged.md:$(jqr "$rt" .source)"
[[ "$(jqr "$rt" .reviewed)" == "false" ]] || die "还没校对过,reviewed 应为 false"
text=$(jqr "$rt" .text)
grep -q '<!-- page: 0 -->' <<<"$text" || die "校对文本里没有页标记(origin_ref 的页码就靠它)"
grep -q "/api/files/parses/$DOC/images/" <<<"$text" || die "图片路径没有被改写成文件服务 URL"
grep -q '](images/' <<<"$text" && die "还残留未改写的相对路径"
IMG=$(jqr "$rt" '.images[0]')
ok "source=paged.md,页尺寸 $(jqr "$rt" '.pages | length') 页,图片 $(jqr "$rt" '.images | length') 张,页标记与图片 URL 均正确"

step "5 图片端点(GET /api/files/...)"
hdr=$(curl -sS -o /dev/null -D - "$API/api/files/parses/$DOC/images/$IMG")
grep -q '200' <<<"$(head -n1 <<<"$hdr")" || die "图片端点没返回 200:$(head -n1 <<<"$hdr")"
grep -qi 'content-type: image/jpeg' <<<"$hdr" || die "content-type 不是 image/jpeg:$hdr"
ok "200 + image/jpeg + $(grep -i content-length <<<"$hdr" | tr -d '\r')"
code=$(curl -sS -o /dev/null -w '%{http_code}' "$API/api/files/parses/$DOC/images/..%2f..%2fparse_result.json")
[[ "$code" == "404" || "$code" == "400" ]] || die "路径穿越应被拒,实得 $code"
ok "路径穿越被拒($code)"

step "6 写回校对文本(PUT),抽取应改用 reviewed.md"
# 真删掉一段:模拟人工校对时删页眉页脚。用文本前 6000 字符(含前两页),抽取快一点也便宜一点
edited=$(printf '%s' "$text" | head -c 6000)
payload=$(jq -n --arg t "$edited" '{text:$t}')
resp=$(curl -sS -w '\n%{http_code}' -X PUT -H 'Content-Type: application/json' -d "$payload" \
  "$API/api/exact-qa/documents/$DOC/review-text")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 200 "$code" "保存校对文本" "$body"
[[ "$(jqr "$body" .source)" == "reviewed.md" ]] || die "保存后应读 reviewed.md:$(jqr "$body" .source)"
[[ "$(jqr "$body" .reviewed)" == "true" ]] || die "reviewed 应为 true"
ok "reviewed.md 已落盘,再读回来就是它(paged.md 保留可对比)"

step "7 确认开始抽取(POST confirm-extract)"
resp=$(curl -sS -w '\n%{http_code}' -X POST "$API/api/exact-qa/documents/$DOC/confirm-extract")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 200 "$code" "确认抽取" "$body"
EXTRACT_JOB=$(jqr "$body" .job_id)
ok "extract_job=$EXTRACT_JOB"
resp=$(curl -sS -w '\n%{http_code}' -X POST "$API/api/exact-qa/documents/$DOC/confirm-extract")
code=$(tail -n1 <<<"$resp")
expect 409 "$code" "重复确认抽取" "$(sed '$d' <<<"$resp")"
ok "重复确认被拒(409 already_extracted)—— 否则同一份文档会出两批候选"

step "8 轮询抽取 Job(上限 ${EXTRACT_TIMEOUT}s,真调 gpt-5 + gpt-5-mini)"
for ((i=0; i<EXTRACT_TIMEOUT; i+=5)); do
  job=$(curl -sS "$API/api/jobs/$EXTRACT_JOB")
  st=$(jqr "$job" .status)
  [[ "$st" == "review" || "$st" == "failed" ]] && break
  printf '\r  %ss status=%s step=%s progress=%s ' "$i" "$st" "$(jqr "$job" .current_step)" "$(jqr "$job" .progress)"
  sleep 5
done
printf '\n'
[[ "$st" == "review" ]] || die "抽取失败:$(jqr "$job" '.error // .status')"
echo "$job" | jq -r '.step_logs[] | "  · \(.step): \(.message)"'
ok "抽取完成,job 停在 review 等人采纳"

step "9 列候选(走 S0 通用审核接口)"
cands=$(curl -sS "$API/api/staging?job_id=$EXTRACT_JOB&limit=500")
N=$(jqr "$cands" .total)
[[ "$N" -gt 0 ]] || die "一条候选都没有"
first=$(jqr "$cands" '.items[0].id'); second=$(jqr "$cands" '.items[1].id')
echo "$cands" | jq -r '.items[:3][] | "  · [\(.confidence)] \(.payload.standard_question)"'
for f in standard_question answer similar_questions keywords; do
  echo "$cands" | jq -e ".items[0].payload | has(\"$f\")" >/dev/null || die "payload 缺 $f"
done
echo "$cands" | jq -e '.items[0].origin_ref | has("quote") and has("page_idx")' >/dev/null \
  || die "origin_ref 缺 quote/page_idx"
ok "$N 条候选,payload 与 origin_ref 字段齐全"

step "10 采纳一条(采纳即发布:写正式表 + 建向量索引)"
before=$(curl -sS "$API/api/exact-qa/items?limit=500" | jq -r .total)
resp=$(curl -sS -w '\n%{http_code}' -X POST "$API/api/exact-qa/candidates/$first/accept")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 200 "$code" "采纳" "$body"
[[ "$(jqr "$body" .published)" == "true" ]] || die "采纳后 published 应为 true"
[[ "$(jqr "$body" .review_status)" == "approved" ]] || die "采纳后状态应为 approved"
FACES=$(jqr "$body" .published_ref.index_faces)
ok "published_ref=$(jqr "$body" '.published_ref | {table,index_faces} | tostring')"
resp=$(curl -sS -w '\n%{http_code}' -X POST "$API/api/exact-qa/candidates/$first/accept")
expect 409 "$(tail -n1 <<<"$resp")" "重复采纳" "$(sed '$d' <<<"$resp")"
ok "重复采纳被拒(409)—— 不会产生重复知识"

step "11 不采纳一条(理由必填)"
resp=$(curl -sS -w '\n%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"note":""}' \
  "$API/api/exact-qa/candidates/$second/reject")
expect 422 "$(tail -n1 <<<"$resp")" "空理由" "$(sed '$d' <<<"$resp")"
ok "空理由被拒(422)"
resp=$(curl -sS -w '\n%{http_code}' -X POST -H 'Content-Type: application/json' \
  -d '{"note":"smoke: duplicate of another candidate"}' \
  "$API/api/exact-qa/candidates/$second/reject")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 200 "$code" "不采纳" "$body"
[[ "$(jqr "$body" .review_status)" == "rejected" && "$(jqr "$body" .published)" == "false" ]] \
  || die "不采纳应 rejected 且不入库:$body"
ok "rejected,留痕不入库"

# 下线端点(POST /items/{id}/disable)在 smoke_exact_qa_store.py 里验(那里能直接数向量行)
step "12 正式 QA 列表 / 详情"
after=$(curl -sS "$API/api/exact-qa/items?limit=500")
[[ "$(jqr "$after" .total)" -eq $((before + 1)) ]] || die "正式 QA 应 +1(before=$before now=$(jqr "$after" .total))"
ITEM=$(jqr "$after" '.items[0].id')
[[ "$(jqr "$after" '.items[0].index_faces')" -eq "$FACES" ]] || die "索引面行数与采纳时不一致"
echo "$after" | jq -e '.items[0] | has("answer") | not' >/dev/null || die "列表不该带长答案正文"
ok "正式 QA $(jqr "$after" .total) 条,索引面 $FACES 行,列表不含答案正文(列表轻详情重)"
detail=$(curl -sS "$API/api/exact-qa/items/$ITEM")
[[ -n "$(jqr "$detail" .answer)" ]] || die "详情必须带答案"
echo "$detail" | jq -e '.origin_ref | has("quote")' >/dev/null || die "详情必须带 origin_ref(溯源)"
ok "详情带答案与 origin_ref(p$(jqr "$detail" .origin_ref.page_idx))"

step "13 文档漏斗计数"
doc=$(curl -sS "$API/api/exact-qa/documents/$DOC")
echo "  $(jqr "$doc" '.funnel | tostring')  stage=$(jqr "$doc" .stage)"
[[ "$(jqr "$doc" .funnel.candidates)" -eq "$N" ]] || die "漏斗候选数不对"
[[ "$(jqr "$doc" .funnel.accepted)" -eq 1 && "$(jqr "$doc" .funnel.rejected)" -eq 1 ]] \
  || die "漏斗采纳/不采纳数不对"
[[ "$(jqr "$doc" .stage)" == "review_qa" ]] || die "还有 pending,stage 应为 review_qa"
ok "漏斗计数正确,stage=review_qa"

step "14 删除文档(Step 8 的边缘):有已发布问答的不许删"
resp=$(curl -sS -w '\n%{http_code}' -X DELETE "$API/api/exact-qa/documents/$DOC")
code=$(tail -n1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
expect 409 "$code" "删有已发布问答的文档" "$body"
[[ "$(jqr "$body" .error.code)" == "document_has_published_qa" ]] || die "错误码不对:$body"
ok "409 document_has_published_qa —— 正式 QA 的出处不会被删成悬空"

step "15 删一份没采纳过任何东西的文档(正例:传错文件要能自己清掉)"
resp=$(curl -sS -w '\n%{http_code}' -F "file=@$PDF;type=application/pdf" "$API/api/exact-qa/documents")
body=$(sed '$d' <<<"$resp"); expect 201 "$(tail -n1 <<<"$resp")" "再传一份" "$body"
TMPDOC=$(jqr "$body" .document_id); TMPJOB=$(jqr "$body" .job_id)
# qa_parse 没有人工关,跑完直接 published —— 别漏了这个终态,否则白等满 PARSE_TIMEOUT
for ((i=0; i<PARSE_TIMEOUT; i+=3)); do
  st=$(jqr "$(curl -sS "$API/api/jobs/$TMPJOB")" .status)
  [[ "$st" == "published" || "$st" == "succeeded" || "$st" == "review" || "$st" == "failed" ]] && break
  sleep 3
done
resp=$(curl -sS -w '\n%{http_code}' -X DELETE "$API/api/exact-qa/documents/$TMPDOC")
expect 204 "$(tail -n1 <<<"$resp")" "删文档" "$(sed '$d' <<<"$resp")"
expect 404 "$(curl -sS -o /dev/null -w '%{http_code}' "$API/api/exact-qa/documents/$TMPDOC")" \
  "删完再查" ""
# 解析产物目录必须一起没了,否则删的只是数据库里那一行
PARSE_DIR="$(cd "$(dirname "$0")/../.." && pwd)/storage/parses/$TMPDOC"
[[ ! -d "$PARSE_DIR" ]] || die "解析产物目录还在:$PARSE_DIR"
expect 404 "$(curl -sS -o /dev/null -w '%{http_code}' "$API/api/files/documents/$TMPDOC/pdf")" \
  "原件端点" ""
ok "204 + 再查 404 + 解析产物目录与上传原件都清掉了"

printf '\n\033[32m[smoke_s1_api] 全链路通过 ✅\033[0m  document=%s extract_job=%s\n' "$DOC" "$EXTRACT_JOB"
printf '  后续 6e 的 chat 冒烟可直接用这批已采纳的知识\n'
