#!/usr/bin/env bash
# 演示结束,把 AWS 上的东西全部拆掉(本地跑,读 deploy.env + stack.env)。
# 拆四样:实例(连同它的 EBS,DeleteOnTermination=true)、Elastic IP、security group、key pair。
# 默认要你确认;--yes 跳过确认。--keep-key 保留 key pair。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
inf() { printf '  · %s\n' "$1"; }

ASSUME_YES=0; KEEP_KEY=0
for a in "$@"; do case "$a" in --yes|-y) ASSUME_YES=1 ;; --keep-key) KEEP_KEY=1 ;; esac; done

[[ -f deploy.env && -f stack.env ]] || { echo "缺 deploy.env / stack.env,没什么可拆"; exit 1; }
set -a; source ./deploy.env; source ./stack.env; set +a
AWS=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")

say "将要删除(账号 $("${AWS[@]}" sts get-caller-identity --query Account --output text) / $AWS_REGION)"
inf "实例 $INSTANCE_ID(含它的 EBS 卷 —— 库里的数据一并消失)"
inf "Elastic IP $ALLOC_ID($PUBLIC_IP)"
inf "security group $SG_ID"
[[ $KEEP_KEY -eq 0 ]] && inf "key pair $STACK_NAME(本地私钥 $SSH_KEY 保留,自己删)"
if [[ $ASSUME_YES -eq 0 ]]; then
	read -r -p $'\n  确认删除?(输 yes)' ans
	[[ "$ans" == "yes" ]] || { echo "取消"; exit 1; }
fi

say "terminate 实例"
"${AWS[@]}" ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null
"${AWS[@]}" ec2 wait instance-terminated --instance-ids "$INSTANCE_ID"; inf "已终止"

say "释放 Elastic IP"
"${AWS[@]}" ec2 release-address --allocation-id "$ALLOC_ID" >/dev/null && inf "已释放"

say "删 security group"
# 实例刚终止,网卡解绑可能还差几秒,重试几次
for i in $(seq 1 12); do
	"${AWS[@]}" ec2 delete-security-group --group-id "$SG_ID" >/dev/null 2>&1 && { inf "已删"; break; }
	[[ $i -eq 12 ]] && inf "⚠ 删不掉(可能还有网卡占着),稍后手动删 $SG_ID"
	sleep 5
done

if [[ $KEEP_KEY -eq 0 ]]; then
	say "删 key pair"
	"${AWS[@]}" ec2 delete-key-pair --key-name "$STACK_NAME" >/dev/null && inf "已删"
fi

mv stack.env stack.env.terminated 2>/dev/null || true
say "拆完"
echo "别忘了最后一件事:去 OpenAI 后台把这次演示用的 key rotate 掉。"
