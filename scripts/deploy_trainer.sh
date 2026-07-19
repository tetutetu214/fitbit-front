#!/usr/bin/env bash
#
# AIトレーナー Lambda (Amazon Bedrock Nova 2) をデプロイする。
#
# 前提:
#   - AWS CLI v2 が設定済み (AWS_PROFILE / AWS_REGION など)
#   - Bedrockコンソールで Nova 2 のモデルアクセスが有効化済み
#
# 使い方:
#   ./scripts/deploy_trainer.sh
#
# 環境変数で上書き可能:
#   AWS_REGION            (default: us-east-1)
#   TRAINER_FUNCTION_NAME (default: fitbit-trainer)
#   TRAINER_ROLE_NAME     (default: fitbit-trainer-role)
#   TRAINER_MODEL_ID      (default: us.amazon.nova-2-lite-v1:0)
#   TRAINER_ALLOW_ORIGIN  (default: * / 本番はCloudflare PagesのURLを指定)
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="${TRAINER_FUNCTION_NAME:-fitbit-trainer}"
ROLE_NAME="${TRAINER_ROLE_NAME:-fitbit-trainer-role}"
MODEL_ID="${TRAINER_MODEL_ID:-us.amazon.nova-2-lite-v1:0}"
ALLOW_ORIGIN="${TRAINER_ALLOW_ORIGIN:-*}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

cp "$ROOT/lambda/trainer/index.mjs" "$BUILD_DIR/"
(cd "$BUILD_DIR" && zip -q trainer.zip index.mjs)

# --- IAMロール(なければ作成) ------------------------------------------------
if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "IAMロール $ROLE_NAME を作成します..."
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "lambda.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }]
    }' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name bedrock-invoke \
    --policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel"],
        "Resource": [
          "arn:aws:bedrock:*::foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      }]
    }'
  echo "IAMロールの伝播を待機中 (10秒)..."
  sleep 10
fi
ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"

# --- Lambda関数(作成 or 更新) -----------------------------------------------
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Lambda関数 $FUNCTION_NAME を更新します..."
  aws lambda update-function-code --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$BUILD_DIR/trainer.zip" --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
  aws lambda update-function-configuration --function-name "$FUNCTION_NAME" \
    --environment "Variables={MODEL_ID=$MODEL_ID}" --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
else
  echo "Lambda関数 $FUNCTION_NAME を作成します..."
  aws lambda create-function --function-name "$FUNCTION_NAME" \
    --runtime nodejs22.x --architectures arm64 \
    --memory-size 256 --timeout 30 \
    --handler index.handler --role "$ROLE_ARN" \
    --zip-file "fileb://$BUILD_DIR/trainer.zip" \
    --environment "Variables={MODEL_ID=$MODEL_ID}" \
    --region "$REGION" >/dev/null
  aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
fi

# --- Function URL(公開 + CORS) ----------------------------------------------
CORS_CONFIG="{\"AllowOrigins\":[\"$ALLOW_ORIGIN\"],\"AllowMethods\":[\"POST\"],\"AllowHeaders\":[\"content-type\"],\"MaxAge\":86400}"
if aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-url-config --function-name "$FUNCTION_NAME" \
    --auth-type NONE --cors "$CORS_CONFIG" --region "$REGION" >/dev/null
else
  aws lambda create-function-url-config --function-name "$FUNCTION_NAME" \
    --auth-type NONE --cors "$CORS_CONFIG" --region "$REGION" >/dev/null
  aws lambda add-permission --function-name "$FUNCTION_NAME" \
    --statement-id public-function-url \
    --action lambda:InvokeFunctionUrl --principal '*' \
    --function-url-auth-type NONE --region "$REGION" >/dev/null
fi

URL="$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" \
  --region "$REGION" --query FunctionUrl --output text)"

echo ""
echo "デプロイ完了 🎉"
echo "以下を .env (またはCloudflare Pagesの環境変数) に設定してください:"
echo ""
echo "  VITE_TRAINER_API_URL=$URL"
