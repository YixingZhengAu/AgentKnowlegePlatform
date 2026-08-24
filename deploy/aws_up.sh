#!/usr/bin/env bash
# 在 AWS 上开出这台演示机(本地跑,读 deploy.env)。只碰四种资源:
#   key pair(私钥落 ~/.ssh)、security group、EC2 实例、Elastic IP。
# 幂等:已经开过就复用,不会重复创建。产出 deploy/stack.env(实例 id / 公网 IP / 站点地址)。
#
# 用法:cd deploy && ./aws_up.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
inf() { printf '  · %s\n' "$1"; }
die() { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

[[ -f deploy.env ]] || die "缺 deploy.env"
# shellcheck disable=SC1091
set -a; source ./deploy.env; set +a

: "${AWS_PROFILE:?deploy.env 缺 AWS_PROFILE}"
: "${AWS_REGION:?deploy.env 缺 AWS_REGION}"
STACK_NAME="${STACK_NAME:-knowledge-agent-demo}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t4g.large}"
VOLUME_SIZE_GB="${VOLUME_SIZE_GB:-30}"
SITE_DOMAIN="${SITE_DOMAIN:-}"
KEY_PATH="$HOME/.ssh/${STACK_NAME}.pem"

AWS=(aws --profile "$AWS_PROFILE" --region "$AWS_REGION")

say "账号与区域"
inf "$("${AWS[@]}" sts get-caller-identity --query 'Account' --output text) / $AWS_REGION"

# ===== 1. key pair =====
say "key pair $STACK_NAME"
if "${AWS[@]}" ec2 describe-key-pairs --key-names "$STACK_NAME" >/dev/null 2>&1; then
	inf "已存在"
	[[ -f "$KEY_PATH" ]] || die "AWS 上有 key pair 但本地没有私钥 $KEY_PATH —— 先在控制台删掉那个 key pair 再重跑"
else
	"${AWS[@]}" ec2 create-key-pair --key-name "$STACK_NAME" \
		--query 'KeyMaterial' --output text > "$KEY_PATH"
	chmod 400 "$KEY_PATH"
	inf "新建,私钥 $KEY_PATH(chmod 400)"
fi

# ===== 2. security group =====
say "security group ${STACK_NAME}-sg"
VPC_ID="$("${AWS[@]}" ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[[ "$VPC_ID" == "None" ]] && die "这个区没有 default VPC"
inf "default VPC $VPC_ID"
SG_ID="$("${AWS[@]}" ec2 describe-security-groups \
	--filters "Name=group-name,Values=${STACK_NAME}-sg" "Name=vpc-id,Values=$VPC_ID" \
	--query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)"
if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
	SG_ID="$("${AWS[@]}" ec2 create-security-group --group-name "${STACK_NAME}-sg" \
		--description "Enterprise Knowledge Agent demo box" --vpc-id "$VPC_ID" \
		--query 'GroupId' --output text)"
	inf "新建 $SG_ID"
else
	inf "已存在 $SG_ID"
fi

# 入站只三条:22 限本机公网 IP(会变,所以每次都补一条)、80/443 对全网
MY_IP="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
authorize() {  # authorize <port> <cidr> <说明>
	"${AWS[@]}" ec2 authorize-security-group-ingress --group-id "$SG_ID" \
		--ip-permissions "IpProtocol=tcp,FromPort=$1,ToPort=$1,IpRanges=[{CidrIp=$2,Description=$3}]" \
		>/dev/null 2>&1 && inf "开 $1 <- $2" || inf "$1 <- $2 已在"
}
authorize 22 "${MY_IP}/32" "admin-ssh"
authorize 80 0.0.0.0/0 "http-acme"
authorize 443 0.0.0.0/0 "https"

# ===== 3. 实例 =====
say "EC2 实例"
INSTANCE_ID="$("${AWS[@]}" ec2 describe-instances \
	--filters "Name=tag:Name,Values=$STACK_NAME" "Name=instance-state-name,Values=pending,running,stopped" \
	--query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo None)"
if [[ "$INSTANCE_ID" == "None" || -z "$INSTANCE_ID" ]]; then
	# AMI 走 SSM 公共参数,不写死 ami-xxx(每个区不同、每次更新也不同)
	AMI_ID="$("${AWS[@]}" ssm get-parameters \
		--names /aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id \
		--query 'Parameters[0].Value' --output text)"
	[[ "$AMI_ID" == ami-* ]] || die "取 Ubuntu 24.04 arm64 AMI 失败:$AMI_ID"
	inf "AMI $AMI_ID(Ubuntu 24.04 arm64)"
	INSTANCE_ID="$("${AWS[@]}" ec2 run-instances \
		--image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
		--key-name "$STACK_NAME" --security-group-ids "$SG_ID" \
		--block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${VOLUME_SIZE_GB},VolumeType=gp3,DeleteOnTermination=true}" \
		--metadata-options "HttpTokens=required" \
		--tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$STACK_NAME},{Key=Purpose,Value=interview-demo}]" \
		--query 'Instances[0].InstanceId' --output text)"
	inf "新建 $INSTANCE_ID($INSTANCE_TYPE / ${VOLUME_SIZE_GB}GiB gp3)"
else
	inf "已存在 $INSTANCE_ID"
	STATE="$("${AWS[@]}" ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].State.Name' --output text)"
	[[ "$STATE" == "stopped" ]] && { "${AWS[@]}" ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null; inf "已 start"; }
fi
inf "等实例 running..."
"${AWS[@]}" ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# ===== 4. Elastic IP =====
# 要固定 IP:stop/start 后公网 IP 会变,发给面试官的链接就废了
say "Elastic IP"
ALLOC_ID="$("${AWS[@]}" ec2 describe-addresses --filters "Name=tag:Name,Values=$STACK_NAME" \
	--query 'Addresses[0].AllocationId' --output text 2>/dev/null || echo None)"
if [[ "$ALLOC_ID" == "None" || -z "$ALLOC_ID" ]]; then
	ALLOC_ID="$("${AWS[@]}" ec2 allocate-address --domain vpc \
		--tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$STACK_NAME}]" \
		--query 'AllocationId' --output text)"
	inf "新分配 $ALLOC_ID"
fi
"${AWS[@]}" ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" >/dev/null
PUBLIC_IP="$("${AWS[@]}" ec2 describe-addresses --allocation-ids "$ALLOC_ID" --query 'Addresses[0].PublicIp' --output text)"
inf "公网 IP $PUBLIC_IP(已关联)"

# ===== 5. 站点地址 =====
# 有域名用域名(A 记录要你自己去 DNS 服务商加);没有就用 nip.io,把 IP 编进主机名。
# 不开密码门时,主机名前缀是随机的 —— Caddy 只对这个主机名服务,扫 IP 的人拿不到页面。
if [[ -n "$SITE_DOMAIN" ]]; then
	SITE_ADDRESS="$SITE_DOMAIN"
else
	if grep -q '^SITE_ADDRESS=' stack.env 2>/dev/null; then
		SITE_ADDRESS="$(grep '^SITE_ADDRESS=' stack.env | cut -d= -f2)"   # 复用,别每次换链接
	else
		SITE_ADDRESS="demo-$(openssl rand -hex 3).${PUBLIC_IP//./-}.nip.io"
	fi
fi
inf "站点地址 $SITE_ADDRESS"

cat > stack.env <<EOF
# aws_up.sh 的产出,后续脚本读它。不入库。
INSTANCE_ID=$INSTANCE_ID
ALLOC_ID=$ALLOC_ID
SG_ID=$SG_ID
PUBLIC_IP=$PUBLIC_IP
SITE_ADDRESS=$SITE_ADDRESS
SSH_KEY=$KEY_PATH
SSH_TARGET=ubuntu@$PUBLIC_IP
EOF

say "等 SSH 可用"
for i in $(seq 1 60); do
	if ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		-o ConnectTimeout=5 -o LogLevel=ERROR "ubuntu@$PUBLIC_IP" true 2>/dev/null; then
		inf "SSH 通了(第 ${i} 次尝试)"; break
	fi
	[[ $i -eq 60 ]] && die "SSH 5 分钟内不通。检查 security group 的 22 是否放了你的 IP($MY_IP)"
	sleep 5
done

say "机器就绪"
cat stack.env
echo
echo "下一步:./remote_deploy.sh"
