#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# create_test_users.sh — Create the three ShopSmart test users in Cognito
#
# Creates one Cognito user per seeded ShopSmart customer (C001–C003), each with:
#   - email + verified email (used as the sign-in identifier)
#   - name                (used by Aria to greet the customer)
#   - custom:customer_id  (maps the login to the DynamoDB customerId)
#   - a permanent password (no forced reset on first login)
#
# This is the recommended path: the Cognito console cannot set a custom
# attribute or a permanent password during user creation.
#
# Usage:
#   export USER_POOL_ID=us-east-1_XXXXXXXXX
#   export AWS_REGION=us-east-1            # optional, defaults to us-east-1
#   export USER_PASSWORD='ShopSmart1!'     # optional, defaults to ShopSmart1!
#   bash create_test_users.sh
#
# To target a specific AWS profile:
#   AWS_PROFILE=my-profile bash create_test_users.sh
# -----------------------------------------------------------------------------

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
USER_POOL_ID="${USER_POOL_ID:?  ERROR: USER_POOL_ID environment variable is required}"
USER_PASSWORD="${USER_PASSWORD:-ShopSmart1!}"

# ── Test users: customer_id | email | full name ──────────────────────────────

USERS=(
  "C001|alice@example.com|Alice Johnson"
  "C002|bob@example.com|Bob Smith"
  "C003|carol@example.com|Carol White"
)

echo ""
echo "Creating ShopSmart test users in user pool: $USER_POOL_ID (region: $REGION)"
echo ""

for USER in "${USERS[@]}"; do
  IFS='|' read -r CUSTOMER_ID EMAIL NAME <<< "$USER"

  # Create the user (idempotent: skip if it already exists).
  if aws cognito-idp admin-get-user \
      --user-pool-id "$USER_POOL_ID" \
      --username "$EMAIL" \
      --region "$REGION" >/dev/null 2>&1; then
    echo "  • $EMAIL already exists — updating attributes and password"
    aws cognito-idp admin-update-user-attributes \
      --user-pool-id "$USER_POOL_ID" \
      --username "$EMAIL" \
      --user-attributes \
          Name=email,Value="$EMAIL" \
          Name=email_verified,Value=true \
          Name=name,Value="$NAME" \
          Name="custom:customer_id",Value="$CUSTOMER_ID" \
      --region "$REGION"
  else
    aws cognito-idp admin-create-user \
      --user-pool-id "$USER_POOL_ID" \
      --username "$EMAIL" \
      --user-attributes \
          Name=email,Value="$EMAIL" \
          Name=email_verified,Value=true \
          Name=name,Value="$NAME" \
          Name="custom:customer_id",Value="$CUSTOMER_ID" \
      --message-action SUPPRESS \
      --region "$REGION" >/dev/null
  fi

  # Set a permanent password so the first login does not force a reset.
  aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$EMAIL" \
    --password "$USER_PASSWORD" \
    --permanent \
    --region "$REGION"

  echo "  ✓ $CUSTOMER_ID — $NAME ($EMAIL)"
done

echo ""
echo "Done. All three users can sign in with password: $USER_PASSWORD"
echo ""
