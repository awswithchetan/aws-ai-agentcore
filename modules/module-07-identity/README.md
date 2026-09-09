# Module 07 — Identity: Auth Done Right

In this module you will add **real authentication** to Aria. Instead of the
manual Customer ID text input from Module 06, customers will log in via
**Amazon Cognito**. The Streamlit UI gets a signed JWT from Cognito, sends it
as a Bearer token, and AgentCore Runtime validates it before the request ever
reaches your agent code.

By the end of this module, Aria knows *who* she is talking to with
cryptographic certainty — no more trusting whatever the client says.

---

## What You Will Build

```
aria-agent/
├── agent.py           # Updated — reads identity from JWT claims (Authorization header)
├── config.py          # Updated — loads /aria/cognito_user_pool_id from SSM
└── identity/
    └── jwt.py         # NEW — decodes the Authorization header and extracts claims

streamlit-ui/
└── app.py             # Updated — Cognito login replaces Customer ID text input
```

<details>
<summary>How This Differs from Module 06</summary>

| | Module 06 — Memory | Module 07 — Identity |
|---|---|---|
| Who is the customer? | Whatever the client types in the sidebar | Verified Cognito JWT — cryptographically signed |
| Customer ID source | `payload["customer_id"]` | JWT `sub` claim, validated by AgentCore Runtime |
| Customer name source | Memory only | JWT `name` claim — always accurate |
| Trust model | Trust the client | Trust the IdP |
| Replay/spoofing risk | High — anyone can type any ID | None — tokens expire and are signed |

</details>

<details>
<summary>How AgentCore Identity (Inbound Auth) works</summary>

```
Streamlit UI
  │ 1. User logs in via Cognito hosted UI
  │ 2. UI receives id_token (JWT) from Cognito
  │ 3. Every invoke_agent_runtime call includes:
  │       Authorization: Bearer <id_token>
  ▼
AgentCore Runtime (Inbound JWT Authorizer)
  │ 4. Runtime fetches Cognito public keys from discovery URL
  │ 5. Validates signature, expiry, audience, client
  │ 6. If valid: forwards Authorization header to agent code
  │    If invalid: returns 401 — agent code never runs
  ▼
agent.py
  │ 7. Decodes JWT (no signature check needed — Runtime already validated)
  │ 8. Extracts sub (= customer_id), name, email
  │ 9. Uses sub as actor_id for memory scoping
  │    Uses name to personalise responses
  ▼
Response returned to Streamlit UI
```

</details>

---

## Step 1 — Create the Cognito User Pool

### Via AWS Console

1. Go to **AWS Console → Amazon Cognito → User pools → Create user pool**

2. **Configure sign-in experience**:
   - **Cognito user pool sign-in options**: check **Email**
   - Click **Next**

3. **Configure security requirements**:
   - Password policy: leave as default (Cognito defaults)
   - MFA: **No MFA** (keep it simple for the course)
   - Click **Next**

4. **Configure sign-up experience**:
   - Self-registration: **Enable** (allows users to sign up)
   - Required attributes: add **name** (so Aria can greet customers)
   - Click **Next**

5. **Configure message delivery**:
   - Email provider: **Send email with Cognito** (free tier, no SES setup)
   - Click **Next**

6. **Integrate your app**:
   - **User pool name**: `shopsmart-users`
   - **Hosted authentication pages**: ✅ **Use the Cognito Hosted UI**
   - **Domain**: choose **Use a Cognito domain**, enter a unique prefix e.g. `shopsmart-auth-<your-account-id>`
   - **App type**: **Public client**
   - **App client name**: `shopsmart-streamlit`
   - **Client secret**: **Don't generate a client secret** (public client)
   - **Allowed callback URLs**: `http://localhost:8501` (Streamlit local URL)
   - **Allowed sign-out URLs**: `http://localhost:8501`
   - **OAuth 2.0 grant types**: check **Authorization code grant**
   - **OpenID Connect scopes**: check **OpenID**, **Email**, **Profile**
   - Click **Next**

7. Review and click **Create user pool**

8. Note down:
   - **User Pool ID** (e.g. `us-east-1_XXXXXXXXX`)
   - **App client ID** (from the App clients tab)
   - **Cognito domain** (e.g. `https://shopsmart-auth-<id>.auth.us-east-1.amazoncognito.com`)

### Via CLI (Optional)

<details>
<summary>Create user pool via CLI</summary>

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create user pool
USER_POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name shopsmart-users \
  --policies '{"PasswordPolicy":{"MinimumLength":8,"RequireUppercase":true,"RequireLowercase":true,"RequireNumbers":true,"RequireSymbols":false}}' \
  --schema '[{"Name":"name","AttributeDataType":"String","Required":true,"Mutable":true}]' \
  --auto-verified-attributes email \
  --username-attributes email \
  --region $AWS_REGION \
  --query 'UserPool.Id' --output text)
echo "User Pool ID: $USER_POOL_ID"

# Create a Cognito domain
DOMAIN_PREFIX="shopsmart-auth-${AWS_ACCOUNT_ID}"
aws cognito-idp create-user-pool-domain \
  --domain $DOMAIN_PREFIX \
  --user-pool-id $USER_POOL_ID \
  --region $AWS_REGION

# Create app client (public, no secret)
CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name shopsmart-streamlit \
  --no-generate-secret \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers COGNITO \
  --callback-urls '["http://localhost:8501"]' \
  --logout-urls '["http://localhost:8501"]' \
  --region $AWS_REGION \
  --query 'UserPoolClient.ClientId' --output text)
echo "App Client ID: $CLIENT_ID"

export USER_POOL_ID CLIENT_ID
export COGNITO_DOMAIN="https://${DOMAIN_PREFIX}.auth.${AWS_REGION}.amazoncognito.com"
echo "Cognito Domain: $COGNITO_DOMAIN"
```

</details>

---

## Step 2 — Create Test Users

Create a user for each ShopSmart test customer. The **username** (sub) must
match the `customerId` used in DynamoDB so Aria can look up orders by the
JWT's `sub` claim.

### Via AWS Console

1. Go to your `shopsmart-users` User Pool → **Users → Create user**
2. Create three users:

| Username (sub) | Email | Name | Temporary password |
|---|---|---|---|
| `C001` | `alice@example.com` | `Alice Johnson` | `ShopSmart1!` |
| `C002` | `bob@example.com` | `Bob Smith` | `ShopSmart1!` |
| `C003` | `carol@example.com` | `Carol White` | `ShopSmart1!` |

3. For each user:
   - **Send an invitation**: unchecked (we'll set permanent passwords via CLI)
   - After creating, select the user → **Actions → Reset password** → set a permanent password

### Via CLI (Optional)

<details>
<summary>Create test users via CLI</summary>

```bash
# Requires USER_POOL_ID to be set from Step 1

for USER in "C001|alice@example.com|Alice Johnson" \
            "C002|bob@example.com|Bob Smith" \
            "C003|carol@example.com|Carol White"; do
  IFS='|' read -r USERNAME EMAIL NAME <<< "$USER"

  aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username $USERNAME \
    --user-attributes \
        Name=email,Value=$EMAIL \
        Name=email_verified,Value=true \
        Name=name,Value="$NAME" \
    --message-action SUPPRESS \
    --region $AWS_REGION

  aws cognito-idp admin-set-user-password \
    --user-pool-id $USER_POOL_ID \
    --username $USERNAME \
    --password "ShopSmart1!" \
    --permanent \
    --region $AWS_REGION

  echo "Created user: $USERNAME ($NAME)"
done
```

</details>

---

## Step 3 — Configure AgentCore Runtime Inbound JWT Authorizer

The Runtime needs to know which Cognito User Pool to trust. You configure
this with a **Custom JWT Authorizer** on the Runtime itself — AgentCore fetches
Cognito's public keys automatically from the discovery URL and validates every
incoming Bearer token.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → aria**
2. Click **Edit**
3. Scroll to **Inbound authorization** → **Add authorizer**
4. Configure:
   - **Authorizer type**: Custom JWT
   - **Discovery URL**: `https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>/.well-known/openid-configuration`
   - **Allowed audiences**: enter your **App client ID** from Step 1
   - **Allowed clients**: enter your **App client ID** from Step 1
5. Under **Request header allowlist**, add `Authorization`

   > This is what allows the JWT to be forwarded into your agent code. Without
   > this, the Runtime strips the Authorization header after validating it.

6. Click **Save**

### Via CLI (Optional)

<details>
<summary>Configure JWT authorizer via CLI</summary>

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

# Get current runtime ID
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaHarnessExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --authorization-configuration "{
    \"customJWTAuthorizer\": {
      \"discoveryUrl\": \"https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration\",
      \"allowedAudiences\": [\"${CLIENT_ID}\"],
      \"allowedClients\": [\"${CLIENT_ID}\"]
    }
  }" \
  --request-header-configuration "{\"requestHeaderAllowlist\": [\"Authorization\"]}" \
  --region $AWS_REGION
```

</details>

---

## Step 4 — Add Cognito Config to SSM

Add the Cognito User Pool ID and App Client ID to SSM so the agent and
Streamlit UI can load them without hardcoding.

### Via AWS Console

Create these parameters in **Systems Manager → Parameter Store**:

| Name | Value |
|---|---|
| `/aria/cognito_user_pool_id` | your User Pool ID (e.g. `us-east-1_XXXXXXXXX`) |
| `/aria/cognito_client_id` | your App Client ID |
| `/aria/cognito_domain` | your Cognito domain (e.g. `https://shopsmart-auth-<id>.auth.us-east-1.amazoncognito.com`) |

### Via CLI (Optional)

<details>
<summary>Add Cognito parameters via CLI</summary>

```bash
for PARAM in \
  "/aria/cognito_user_pool_id|${USER_POOL_ID}" \
  "/aria/cognito_client_id|${CLIENT_ID}" \
  "/aria/cognito_domain|${COGNITO_DOMAIN}"; do
  IFS='|' read -r NAME VALUE <<< "$PARAM"
  aws ssm put-parameter \
    --name "$NAME" \
    --value "$VALUE" \
    --type String \
    --overwrite \
    --region $AWS_REGION
  echo "Set $NAME"
done
```

</details>

---

## Step 5 — Update the Agent

Copy the Module 07 agent files to `aria-agent/`:

```bash
cp modules/module-07-identity/agent.py aria-agent/agent.py
cp modules/module-07-identity/config.py aria-agent/config.py
cp -r modules/module-07-identity/identity aria-agent/
```

Verify:

```bash
ls aria-agent/identity/
# jwt.py
```

<details>
<summary>What changed in agent.py</summary>

The Module 07 agent replaces the `payload["customer_id"]` approach with JWT
claims extracted from the `Authorization` header. The `context` object from
AgentCore Runtime carries the forwarded request headers:

```python
# Module 06 — trust the payload
customer_id = payload.get("customer_id", "anonymous")

# Module 07 — trust the verified JWT
from identity.jwt import extract_identity
identity = extract_identity(context)
customer_id = identity.customer_id   # = JWT sub claim
customer_name = identity.name        # = JWT name claim
customer_email = identity.email      # = JWT email claim
```

The system prompt injection now uses the customer's actual name from the JWT
instead of just the ID:

```python
system_prompt = SYSTEM_PROMPT + f"""

## Current customer
Customer ID: {customer_id}
Name: {customer_name}
Email: {customer_email}

Address them by name. Use their customer ID directly with tools — do not ask for it.
"""
```

</details>

<details>
<summary>What identity/jwt.py does</summary>

`extract_identity` reads the `Authorization` header from `context.request_headers`,
base64-decodes the JWT payload (no signature check — the Runtime already validated it),
and returns a typed `CustomerIdentity` object:

```python
@dataclass
class CustomerIdentity:
    customer_id: str    # JWT sub claim — matches customerId in DynamoDB
    name: str           # JWT name claim
    email: str          # JWT email claim
    raw_claims: dict    # full decoded claims for debugging

def extract_identity(context) -> CustomerIdentity:
    headers = getattr(context, "request_headers", {}) or {}
    auth = headers.get("Authorization") or headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return CustomerIdentity(customer_id="anonymous", name="", email="", raw_claims={})
    token = auth.split(" ", 1)[1]
    # Decode without verification — Runtime already validated the signature
    claims = json.loads(base64.b64decode(token.split(".")[1] + "=="))
    return CustomerIdentity(
        customer_id=claims.get("sub", "anonymous"),
        name=claims.get("name", ""),
        email=claims.get("email", ""),
        raw_claims=claims,
    )
```

</details>

---

## Step 6 — Update the Streamlit UI

```bash
cp modules/module-07-identity/app.py streamlit-ui/app.py
```

<details>
<summary>What changed from Module 06</summary>

The manual Customer ID text input is replaced by a **Cognito login flow**:

- Sidebar shows a **Sign in with ShopSmart** button
- Clicking it redirects to the Cognito Hosted UI login page
- After login, Cognito redirects back to Streamlit with an authorization code
- Streamlit exchanges the code for an `id_token` (JWT)
- Every `invoke_agent_runtime` call now sends `Authorization: Bearer <id_token>`
- The sidebar shows the logged-in customer's name and email from the token claims
- A **Sign out** button clears the token and redirects to Cognito's logout endpoint

The `ARIA_HARNESS_ARN`, `AWS_REGION`, and Cognito parameters are loaded from
SSM at startup — no hardcoding required.

</details>

---

## Step 7 — Rebuild and Deploy

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..

RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaHarnessExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 07 — Identity" \
  --region $AWS_REGION
```

Wait for the runtime status to return to **Ready**.

---

## Step 8 — Test

### Run Streamlit

```bash
export AWS_REGION=us-east-1
streamlit run streamlit-ui/app.py
```

Open `http://localhost:8501`.

### Login flow

1. Click **Sign in with ShopSmart** in the sidebar
2. You are redirected to the Cognito Hosted UI
3. Log in as `C001` / `ShopSmart1!`
4. You are redirected back to Streamlit — the sidebar now shows **Alice Johnson**
5. Send a message: `Hi!` — Aria should greet Alice by name immediately

### Verify the token is being validated

To confirm the Runtime is rejecting unauthenticated requests, try invoking
without a token:

```bash
RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region us-east-1 \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeArn" \
  --output text)

# This should return 401 Unauthorized
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn $RUNTIME_ARN \
  --runtime-session-id "test-no-auth" \
  --payload '{"prompt":"hello"}' \
  --region us-east-1
```

### Test all three customers

| Login | Expected greeting |
|---|---|
| `C001` / `ShopSmart1!` | "Hi Alice! How can I help you?" |
| `C002` / `ShopSmart1!` | "Hi Bob! How can I help you?" |
| `C003` / `ShopSmart1!` | "Hi Carol! How can I help you?" |

---

<details>
<summary>Troubleshooting</summary>

**401 Unauthorized on all requests**

- Check the JWT authorizer discovery URL in the Runtime config — it must include
  `/.well-known/openid-configuration` at the end.
- Check that the `allowedAudiences` and `allowedClients` match the App Client ID
  exactly (copy-paste, no trailing spaces).

**`Authorization` header not reaching agent code**

- Confirm `Authorization` is in the **Request header allowlist** on the Runtime.
  Without this, the Runtime strips the header after validation.
- Check CloudWatch logs for `extract_identity` — look for `"customer_id": "anonymous"`
  which means the header arrived empty.

**Cognito redirect loop / callback URL mismatch**

- The callback URL in Cognito must exactly match `http://localhost:8501` (no trailing slash).
- If running on a different port, update the callback URL in the Cognito App Client settings.

**User can log in but Aria doesn't know their name**

- Check that the `name` attribute was set when the user was created.
- In the Cognito console, open the user → verify the `name` attribute is populated.
- Re-issue the token by logging out and back in — cached tokens won't have new attributes.

**Token expired mid-session**

- Cognito `id_token` expires in 1 hour by default.
- The Streamlit UI should detect a 401 response and redirect to login.
- You can extend the token expiry in the App Client settings (up to 24 hours).

</details>

---

<details>
<summary>What You Learned</summary>

- How AgentCore's inbound JWT authorizer validates tokens before your agent code runs
- How to configure a Cognito User Pool as the identity provider for AgentCore Runtime
- How the `Authorization` header allowlist works and why it's required
- How to extract verified identity claims from the forwarded JWT in agent code
- Why `sub` (not `email` or `name`) is the stable identifier to use as `actor_id`
- How the Streamlit authorization code flow works with Cognito Hosted UI
- The difference between inbound auth (who can call the agent) and outbound auth (what the agent can call)

</details>

---

## Next Step

Proceed to [Module 08 — Policy](../module-08-policy/README.md) where you will
add Cedar-based guardrails to control what Aria is allowed to do — and for whom.
