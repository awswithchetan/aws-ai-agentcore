#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# put_ssm_params.sh — Create/update Aria's SSM parameters
#
# Run this once per environment (dev, staging, prod) after setting the values
# below. Re-run anytime to update a value — it won't rebuild or redeploy the
# agent container.
#
# Usage:
#   export KNOWLEDGE_BASE_ID=kb-XXXXXXXXXX
#   export AWS_REGION=us-east-1          # optional, defaults to us-east-1
#   bash scripts/put_ssm_params.sh
#
# To target a specific AWS profile:
#   AWS_PROFILE=my-profile bash scripts/put_ssm_params.sh
# -----------------------------------------------------------------------------

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PREFIX="/aria"

# ── Values — edit these or override via environment variables ─────────────────

MODEL_ID="${MODEL_ID:-us.anthropic.claude-sonnet-4-6}"
KNOWLEDGE_BASE_ID="${KNOWLEDGE_BASE_ID:?  ERROR: KNOWLEDGE_BASE_ID environment variable is required}"
KB_NUM_RESULTS="${KB_NUM_RESULTS:-5}"
API_BASE_URL="${API_BASE_URL:-}"

# ── Helper ────────────────────────────────────────────────────────────────────

put_param() {
  local name="$1"
  local value="$2"
  local type="${3:-String}"          # String | SecureString

  aws ssm put-parameter \
    --region "$REGION" \
    --name "${PREFIX}/${name}" \
    --value "$value" \
    --type "$type" \
    --overwrite \
    --output text \
    --query "Version" \
    | xargs -I{} echo "  ✓ ${PREFIX}/${name}  (version {})"
}

# ── Create / update parameters ────────────────────────────────────────────────

echo ""
echo "Writing Aria SSM parameters to region: $REGION"
echo "Prefix: $PREFIX"
echo ""

put_param "region"            "$REGION"
put_param "model_id"          "$MODEL_ID"
put_param "knowledge_base_id" "$KNOWLEDGE_BASE_ID"
put_param "kb_num_results"    "$KB_NUM_RESULTS"
if [ -n "$API_BASE_URL" ]; then
  put_param "api_base_url"    "$API_BASE_URL"
fi

echo ""
echo "Done. To change a value without redeploying, re-run this script with"
echo "the updated variable and restart the agent runtime (or wait for the"
echo "next cold start — config is read once at container startup)."
echo ""
