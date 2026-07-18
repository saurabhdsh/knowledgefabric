#!/usr/bin/env bash
# Provision and deploy Weave on a cost-conscious EC2 instance with Bedrock IAM.
set -Eeuo pipefail

REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"
VOLUME_GB="${VOLUME_GB:-50}"
INSTANCE_NAME="${INSTANCE_NAME:-weave-server}"
ROLE_NAME="${ROLE_NAME:-WeaveEC2BedrockRole}"
POLICY_NAME="${POLICY_NAME:-WeaveBedrockAccess}"
PROFILE_NAME="${PROFILE_NAME:-WeaveEC2BedrockProfile}"
SG_NAME="${SG_NAME:-weave-sg}"
HTTP_CIDR="${HTTP_CIDR:-0.0.0.0/0}"
REPO_URL="${REPO_URL:-https://github.com/saurabhdsh/knowledgefabric.git}"
STATE_DIR="${HOME}/.weave/ec2"
KEY_DIR="${STATE_DIR}/keys"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
KEY_NAME="${KEY_NAME:-weave-ec2-${TIMESTAMP}}"
KEY_FILE="${KEY_DIR}/${KEY_NAME}.pem"
STATE_FILE="${STATE_DIR}/latest-deployment.env"

log() { printf '\n[weave-deploy] %s\n' "$*"; }
die() { printf '\n[weave-deploy] ERROR: %s\n' "$*" >&2; exit 1; }

command -v aws >/dev/null 2>&1 || die "AWS CLI is not installed."
command -v ssh >/dev/null 2>&1 || die "ssh is not installed."
command -v curl >/dev/null 2>&1 || die "curl is not installed."

export AWS_EC2_METADATA_DISABLED=true

log "Verifying AWS identity in ${REGION}..."
IDENTITY="$(aws sts get-caller-identity --region "${REGION}" --output json)" ||
  die "AWS authentication failed. Run 'aws configure' (or SSO login) and retry."
ACCOUNT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Account"])' <<<"${IDENTITY}")"
CALLER_ARN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["Arn"])' <<<"${IDENTITY}")"
printf 'Account: %s\nCaller:  %s\nRegion:  %s\n' "${ACCOUNT_ID}" "${CALLER_ARN}" "${REGION}"

printf '\nThis creates billable AWS resources:\n'
printf '  EC2: %s, %s GB gp3\n  URL: public HTTP on port 80\n  SSH: restricted to this Mac public IP\n' \
  "${INSTANCE_TYPE}" "${VOLUME_GB}"
if [[ "${AUTO_APPROVE:-false}" != "true" ]]; then
  read -r -p "Type DEPLOY to continue: " CONFIRM
  [[ "${CONFIRM}" == "DEPLOY" ]] || die "Deployment cancelled."
fi

mkdir -p "${KEY_DIR}"
chmod 700 "${HOME}/.weave" "${STATE_DIR}" "${KEY_DIR}" 2>/dev/null || true

POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"
TRUST_FILE="$(mktemp)"
POLICY_FILE="$(mktemp)"
trap 'rm -f "${TRUST_FILE}" "${POLICY_FILE}"' EXIT

cat >"${POLICY_FILE}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
JSON

cat >"${TRUST_FILE}" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

log "Creating/reusing Bedrock IAM policy..."
if ! aws iam get-policy --policy-arn "${POLICY_ARN}" >/dev/null 2>&1; then
  aws iam create-policy \
    --policy-name "${POLICY_NAME}" \
    --description "Allow Weave EC2 to invoke Amazon Bedrock models" \
    --policy-document "file://${POLICY_FILE}" >/dev/null
fi

log "Creating/reusing EC2 IAM role and instance profile..."
if ! aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --description "EC2 role for Weave Bedrock deployment" \
    --assume-role-policy-document "file://${TRUST_FILE}" >/dev/null
fi
aws iam attach-role-policy --role-name "${ROLE_NAME}" --policy-arn "${POLICY_ARN}"
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"

if ! aws iam get-instance-profile --instance-profile-name "${PROFILE_NAME}" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "${PROFILE_NAME}" >/dev/null
fi
PROFILE_HAS_ROLE="$(aws iam get-instance-profile \
  --instance-profile-name "${PROFILE_NAME}" \
  --query "length(InstanceProfile.Roles[?RoleName=='${ROLE_NAME}'])" \
  --output text)"
if [[ "${PROFILE_HAS_ROLE}" == "0" ]]; then
  aws iam add-role-to-instance-profile \
    --instance-profile-name "${PROFILE_NAME}" \
    --role-name "${ROLE_NAME}"
fi

log "Resolving default VPC, subnet, and Amazon Linux 2023 AMI..."
VPC_ID="$(aws ec2 describe-vpcs \
  --region "${REGION}" \
  --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)"
[[ -n "${VPC_ID}" && "${VPC_ID}" != "None" ]] ||
  die "No default VPC found in ${REGION}. Create/select a VPC before retrying."

SUBNET_ID="$(aws ec2 describe-subnets \
  --region "${REGION}" \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
  --query 'Subnets[0].SubnetId' --output text)"
[[ -n "${SUBNET_ID}" && "${SUBNET_ID}" != "None" ]] ||
  die "No default subnet found in ${VPC_ID}."

AMI_ID="$(aws ssm get-parameter \
  --region "${REGION}" \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameter.Value' --output text)"

SSH_CIDR="${SSH_CIDR:-$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')/32}"
[[ "${SSH_CIDR}" =~ ^[0-9a-fA-F:.]+/[0-9]+$ ]] || die "Could not determine SSH CIDR."

log "Creating/reusing security group (${SG_NAME})..."
SG_ID="$(aws ec2 describe-security-groups \
  --region "${REGION}" \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${SG_NAME}" \
  --query 'SecurityGroups[0].GroupId' --output text)"
if [[ -z "${SG_ID}" || "${SG_ID}" == "None" ]]; then
  SG_ID="$(aws ec2 create-security-group \
    --region "${REGION}" \
    --vpc-id "${VPC_ID}" \
    --group-name "${SG_NAME}" \
    --description "Weave demo server: SSH restricted, HTTP public" \
    --query GroupId --output text)"
fi
aws ec2 authorize-security-group-ingress \
  --region "${REGION}" --group-id "${SG_ID}" \
  --protocol tcp --port 22 --cidr "${SSH_CIDR}" >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress \
  --region "${REGION}" --group-id "${SG_ID}" \
  --protocol tcp --port 80 --cidr "${HTTP_CIDR}" >/dev/null 2>&1 || true

EXISTING_INSTANCE="$(aws ec2 describe-instances \
  --region "${REGION}" \
  --filters "Name=tag:Name,Values=${INSTANCE_NAME}" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)"
if [[ -n "${EXISTING_INSTANCE}" && "${EXISTING_INSTANCE}" != "None" ]]; then
  die "An instance named ${INSTANCE_NAME} already exists (${EXISTING_INSTANCE}). Terminate/rename it or set INSTANCE_NAME."
fi

log "Creating SSH key pair (${KEY_FILE})..."
aws ec2 create-key-pair \
  --region "${REGION}" \
  --key-name "${KEY_NAME}" \
  --key-type rsa \
  --key-format pem \
  --query KeyMaterial --output text >"${KEY_FILE}"
chmod 400 "${KEY_FILE}"

# Instance-profile propagation can take a few seconds after initial creation.
sleep 10

log "Launching ${INSTANCE_TYPE} with ${VOLUME_GB} GB gp3..."
INSTANCE_ID="$(aws ec2 run-instances \
  --region "${REGION}" \
  --image-id "${AMI_ID}" \
  --instance-type "${INSTANCE_TYPE}" \
  --key-name "${KEY_NAME}" \
  --security-group-ids "${SG_ID}" \
  --subnet-id "${SUBNET_ID}" \
  --associate-public-ip-address \
  --iam-instance-profile "Name=${PROFILE_NAME}" \
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled,HttpPutResponseHopLimit=2" \
  --block-device-mappings \
    "DeviceName=/dev/xvda,Ebs={VolumeSize=${VOLUME_GB},VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}},{Key=Application,Value=Weave},{Key=Environment,Value=demo}]" \
    "ResourceType=volume,Tags=[{Key=Name,Value=${INSTANCE_NAME}-data},{Key=Application,Value=Weave}]" \
  --query 'Instances[0].InstanceId' --output text)"

aws ec2 wait instance-running --region "${REGION}" --instance-ids "${INSTANCE_ID}"
aws ec2 wait instance-status-ok --region "${REGION}" --instance-ids "${INSTANCE_ID}"

log "Allocating and associating Elastic IP..."
ALLOCATION_ID="$(aws ec2 allocate-address \
  --region "${REGION}" --domain vpc \
  --tag-specifications \
    "ResourceType=elastic-ip,Tags=[{Key=Name,Value=${INSTANCE_NAME}-eip},{Key=Application,Value=Weave}]" \
  --query AllocationId --output text)"
ELASTIC_IP="$(aws ec2 describe-addresses \
  --region "${REGION}" --allocation-ids "${ALLOCATION_ID}" \
  --query 'Addresses[0].PublicIp' --output text)"
ASSOCIATION_ID="$(aws ec2 associate-address \
  --region "${REGION}" \
  --instance-id "${INSTANCE_ID}" \
  --allocation-id "${ALLOCATION_ID}" \
  --query AssociationId --output text)"

cat >"${STATE_FILE}" <<EOF
AWS_REGION=${REGION}
INSTANCE_ID=${INSTANCE_ID}
INSTANCE_NAME=${INSTANCE_NAME}
INSTANCE_TYPE=${INSTANCE_TYPE}
SECURITY_GROUP_ID=${SG_ID}
KEY_NAME=${KEY_NAME}
KEY_FILE=${KEY_FILE}
ELASTIC_IP=${ELASTIC_IP}
ALLOCATION_ID=${ALLOCATION_ID}
ASSOCIATION_ID=${ASSOCIATION_ID}
PUBLIC_URL=http://${ELASTIC_IP}
EOF
chmod 600 "${STATE_FILE}"

SSH_OPTS=(-i "${KEY_FILE}" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
log "Waiting for SSH at ${ELASTIC_IP}..."
for _ in $(seq 1 30); do
  if ssh "${SSH_OPTS[@]}" "ec2-user@${ELASTIC_IP}" "true" >/dev/null 2>&1; then
    break
  fi
  sleep 10
done
ssh "${SSH_OPTS[@]}" "ec2-user@${ELASTIC_IP}" "true" >/dev/null 2>&1 ||
  die "EC2 is running, but SSH is unavailable. Deployment state: ${STATE_FILE}"

log "Installing Git, adding 4 GB swap, and cloning Weave..."
ssh "${SSH_OPTS[@]}" "ec2-user@${ELASTIC_IP}" \
  "sudo dnf install -y git && \
   if ! sudo swapon --show | grep -q /swapfile; then \
     sudo dd if=/dev/zero of=/swapfile bs=1M count=4096 status=progress && \
     sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && \
     grep -q '^/swapfile ' /etc/fstab || echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab; \
   fi && \
   if [ -d \"\$HOME/Knowledge-Fabric/.git\" ]; then \
     git -C \"\$HOME/Knowledge-Fabric\" pull --ff-only origin main; \
   else \
     git clone '${REPO_URL}' \"\$HOME/Knowledge-Fabric\"; \
   fi"

log "Building and starting Weave (this can take 10-20 minutes)..."
ssh "${SSH_OPTS[@]}" "ec2-user@${ELASTIC_IP}" \
  "cd \"\$HOME/Knowledge-Fabric\" && \
   sudo env PUBLIC_URL='http://${ELASTIC_IP}' bash scripts/ec2-setup.sh"

log "Verifying services and Bedrock IAM from the backend container..."
ssh "${SSH_OPTS[@]}" "ec2-user@${ELASTIC_IP}" \
  "cd \"\$HOME/Knowledge-Fabric\" && \
   sudo docker compose -f docker-compose.ec2.yml ps && \
   sudo docker compose -f docker-compose.ec2.yml exec -T backend python - <<'PY'
from app.core.config import settings
from app.services.llm.llm_router import llm_router
print('default_provider=', settings.DEFAULT_LLM_PROVIDER)
print('bedrock_enabled=', settings.BEDROCK_ENABLED)
print('bedrock_ready=', llm_router.is_provider_ready('bedrock'))
PY"

log "Waiting for public health endpoint..."
for _ in $(seq 1 30); do
  if curl -fsS "http://${ELASTIC_IP}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 10
done
curl -fsS "http://${ELASTIC_IP}/health" ||
  die "Deployment completed but health check failed. State: ${STATE_FILE}"

cat <<EOF

Weave deployment completed.

URL:         http://${ELASTIC_IP}
Health:      http://${ELASTIC_IP}/health
SSH:         ssh -i "${KEY_FILE}" ec2-user@${ELASTIC_IP}
State file:  ${STATE_FILE}

Default login: Saurabh / admin123
Change the default password immediately after signing in.
EOF
