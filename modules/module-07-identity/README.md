# Module 07 — Identity: Auth Done Right

In this module you will add **real customer authentication**. Instead of the
manual Customer ID text input from Module 06 — where anyone could type any ID
and see that customer's data — customers now log in via **Amazon Cognito**. The
Streamlit UI gets a signed JWT from Cognito, sends it as a Bearer token, and
AgentCore Runtime validates it before the request ever reaches your agent code.

This closes a real security gap. The customer's identity is no longer something
the client claims — it is derived server-side from the verified token. The
agent reads `custom:customer_id` from the JWT claims (never from the request
payload), so a logged-in customer can only ever pull up **their own** orders,
returns, and memory. There is no way for a client to pass someone else's
customer ID and view their data.

By the end of this module, Aria knows *who* she is talking to with
cryptographic certainty — no more trusting whatever the client says.

---

## What You Will Build

```
aria-agent/
├── agent.py           # Updated — reads identity from JWT claims (custom id-token header)
├── config.py          # Updated — loads /aria/cognito_* from SSM
└── identity/
    └── jwt.py         # NEW — decodes the forwarded id token and extracts claims

streamlit-ui/
└── app.py             # Updated — Cognito login replaces Customer ID text input
```

<details>
<summary>How This Differs from Module 06</summary>

| | Module 06 — Memory | Module 07 — Identity |
|---|---|---|
| Who is the customer? | Whatever the client types in the sidebar | Verified Cognito JWT — cryptographically signed |
| Customer ID source | `payload["customer_id"]` | JWT `custom:customer_id` claim, validated by AgentCore Runtime |
| Customer name source | Memory only | JWT `name` claim — always accurate |
| Trust model | Trust the client | Trust the IdP |
| Replay/spoofing risk | High — anyone can type any ID | None — tokens expire and are signed |

</details>

<details>
<summary>How AgentCore Identity (Inbound Auth) works</summary>

```
Streamlit UI
  │ 1. User logs in via Cognito hosted UI (with their email)
  │ 2. UI receives access_token AND id_token from Cognito
  │ 3. Every invocation sends:
  │       Authorization: Bearer <access_token>            (Runtime validates this)
  │       X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token: <id_token>  (identity claims)
  ▼
AgentCore Runtime (Inbound JWT Authorizer)
  │ 4. Runtime fetches Cognito public keys from discovery URL
  │ 5. Validates the access_token signature, expiry, and client_id
  │ 6. If valid: forwards both headers to agent code
  │    If invalid: returns 401 — agent code never runs
  ▼
agent.py
  │ 7. Decodes the id_token from the custom header (no signature check needed)
  │ 8. Extracts custom:customer_id (= C001), name, email
  │ 9. Uses custom:customer_id as actor_id for memory scoping
  │    Uses name to personalise responses
  ▼
Response returned to Streamlit UI
```

> **Downstream API authentication:** Cognito protects the customer-facing
> Streamlit-to-Runtime request. The ShopSmart API is protected separately with
> `AWS_IAM`; AgentCore Gateway signs its API Gateway requests with SigV4 using
> the Gateway service role. The customer's Cognito token is not used as the
> API Gateway credential.

> **Why two tokens?** The Cognito access_token is what the Runtime validates
> (it carries `client_id`), but it doesn't contain user profile claims. The
> id_token carries `name`, `email`, and `custom:customer_id`. We send the
> access_token as the Bearer for validation and the id_token in a custom header
> so the agent can read the profile claims.

</details>

---

## Step 1 — Create the Cognito User Pool

### Via AWS Console

1. Go to **AWS Console → Amazon Cognito → User pools → Create user pool**

2. **Define your application**:
   - Select **Single-page application (SPA)**

3. **Name your application**:
   - **Application name**: `shopsmart-streamlit`

4. **Configure options**:
   - **Sign-in identifiers**: check **Email**
   - **Self-registration**: ☐ disabled

     > We create the three test users manually in Step 2 to match the seeded
     > DynamoDB data. Enabling self-registration would let anyone sign up, but
     > new accounts won't have orders in the database.

   - **Required attributes for sign-up**: open the dropdown and add **name**
     (Aria uses this to greet customers — it must be collected at sign-up)
   - **Return URL**: `http://localhost:8501`
     (Cognito redirects here after login — must match exactly)

5. Click **Create user directory**

6. **Add a custom attribute** for the ShopSmart customer ID.

   Cognito auto-generates `sub` as a UUID — it won't match `C001`/`C002`/`C003`
   in DynamoDB. We use a custom attribute to carry the application customer ID
   alongside the Cognito identity.

   Go to your new user pool → open the **Sign-up** tab → in the **Custom
   attributes** section click **Add custom attributes**:
   - **Name**: `customer_id`  *(Cognito will prefix it — it becomes `custom:customer_id` in the JWT)*
   - **Type**: String
   - **Mutable**: ✅
   - Click **Save changes**

   > Custom attributes are permanent — you cannot rename or remove one after
   > adding it, so enter the name `customer_id` exactly. Cognito also does not
   > allow custom attributes to be marked as required.

7. **Verify the app client can read and write the custom attribute.**

   Go to **App clients → shopsmart-streamlit → Attribute permissions**:
   - Confirm `custom:customer_id` has both **Read** and **Write** enabled.
     Cognito enables both by default for newly added custom attributes, so
     there is usually nothing to change here — just confirm it, and save if
     you make any adjustment.

   > This permission is what lets the app client set `custom:customer_id` when
   > a user is created and include it in the token claims the agent reads.

8. **Verify the app client's OpenID Connect scopes.**

   The SPA quick-create flow doesn't let you choose OAuth scopes, and the
   default set may not include `profile`. The Streamlit login requests
   `openid email profile`, so the app client must allow all three — otherwise
   the hosted UI returns an **invalid request** error on sign-in.

   Go to **App clients → shopsmart-streamlit → Login pages → Edit**:
   - Under **OpenID Connect scopes**, ensure **OpenID**, **Email**, and
     **Profile** are all selected (add **Profile** if it's missing).
   - Click **Save changes**

   > `profile` is what makes the `name` claim available in the token, which Aria
   > uses to greet the customer. Without it, sign-in fails with an invalid
   > request error.

9. Note down from the User Pool detail page:
   - **User Pool ID** — shown at the top (e.g. `us-east-1_XXXXXXXXX`)
   - **App client ID** — under the **App clients** tab
   - **Cognito domain** — under **Branding → Domain**
     (e.g. `https://shopsmart-streamlit-jvklra.auth.us-east-1.amazoncognito.com`)
   - **Discovery URL** — the OpenID Connect discovery endpoint for your pool,
     which you'll need for the Runtime's JWT authorizer in Step 3. It's derived
     from your region and User Pool ID:
     ```
     https://cognito-idp.<region>.amazonaws.com/<USER_POOL_ID>/.well-known/openid-configuration
     ```
     e.g. `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX/.well-known/openid-configuration`

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

Create a user for each ShopSmart test customer. Users log in with their
**email address**. The `custom:customer_id` attribute maps them to the correct
DynamoDB records.

> Unlike the other steps in this module, this one leads with the **CLI**. The
> Cognito console Create-user flow can't set a custom attribute or a permanent
> password in one go — it creates the user with a temporary password (forcing a
> reset on first login) and requires a separate edit to add `custom:customer_id`.
> The CLI sets the email, `name`, `custom:customer_id`, and a permanent password
> in a single pass for all three users.

### Via CLI

Run the helper script in this module directory. It creates all three users with
the email, `name`, `custom:customer_id`, and a permanent password (no forced
reset), and is safe to re-run — it updates existing users instead of failing.

```bash
export USER_POOL_ID=<your-user-pool-id>
export AWS_REGION=us-east-1

bash modules/module-07-identity/create_test_users.sh
```

This creates three users, each logging in with the email/password below:

| Email (username) | Password | name | custom:customer_id |
|---|---|---|---|
| `alice@example.com` | `ShopSmart1!` | `Alice Johnson` | `C001` |
| `bob@example.com` | `ShopSmart1!` | `Bob Smith` | `C002` |
| `carol@example.com` | `ShopSmart1!` | `Carol White` | `C003` |

<details>
<summary>What the script does</summary>

For each of the three customers it runs `admin-create-user` (or
`admin-update-user-attributes` if the user already exists) to set the email,
verified-email flag, `name`, and `custom:customer_id`, then
`admin-set-user-password --permanent` so the first login does not force a
password reset. The Cognito console cannot do either of those during user
creation, which is why this step uses a script.

</details>

<details>
<summary>Via AWS Console (more steps — CLI above is recommended)</summary>

The console can't set the custom attribute or a permanent password during
creation, so it's a two-step process per user and the first login will force a
password reset.

1. Go to your user pool → **Users → Create user**
2. For each user:
   - **Invitation message**: select **Don't send an invitation**
   - **Email address**: e.g. `alice@example.com`
   - **Mark email address as verified**: ✅
   - **Password**: set `ShopSmart1!` (this will be a **temporary** password)
   - Choose **Create**
3. Open each user from the **Users** list → **Edit** **User attributes**, then
   set **both** of these in the same save (the required `name` attribute blocks
   saving if left empty):
   - **name**: e.g. `Alice Johnson`
   - **custom:customer_id**: e.g. `C001`

Use the same email / name / customer_id values shown in the table above. The
first login for each user will prompt for a new password (console-created
passwords are always temporary).

</details>

---

## Step 3 — Configure AgentCore Runtime Inbound JWT Authorizer

The Runtime needs to know which Cognito User Pool to trust. You configure
this with a **Custom JWT Authorizer** on the Runtime itself — AgentCore fetches
Cognito's public keys automatically from the discovery URL and validates every
incoming Bearer token.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → aria**
2. Click **Update runtime**
3. In the **Protocol** selection, choose **HTTP** (Aria is invoked over the
   standard HTTP runtime endpoint).
4. For **Inbound auth type**, select **Use JSON Web Tokens (JWT)**
   (rather than **Use IAM permissions**).
5. Configure the JWT authorizer fields:
   - **Discovery URL**: the OpenID Connect discovery URL you noted in Step 1
     (`https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>/.well-known/openid-configuration`)
   - **Allowed clients**: enter your **App client ID** from Step 1
6. Click **Update runtime**

   > **Do NOT set Allowed audiences.** The Streamlit UI invokes the runtime
   > using the Cognito **access token**, which has no `aud` claim (only
   > `client_id`). If you set an allowed audience, every request fails with
   > `Claim 'aud' value mismatch`. Validate with **Allowed clients** only.
   >
   > You may also see **Allowed Scopes** and **Custom Claims** fields — leave
   > these empty for now.

### Add the Request Headers to the Allowlist (CLI required)

The AWS Console does not currently expose the **Request header allowlist**
setting. You must run this CLI command to allow two headers to be forwarded to
your agent code after the Runtime validates the token:

- `Authorization` — the access token (already validated by the Runtime)
- `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token` — the id token, which
  carries the `name`, `email`, and `custom:customer_id` claims that
  `extract_identity()` reads

> Without this step the Runtime validates the JWT but strips these headers
> before they reach `agent.py` — `extract_identity()` returns anonymous and
> Aria won't know who the customer is.

Fill in your values from Step 1, then run:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export USER_POOL_ID=<your-user-pool-id>      # e.g. us-east-1_XXXXXXXXX
export CLIENT_ID=<your-app-client-id>

# Point ECR_REPO at your agent image repository, then IMAGE_URI adds the tag.
# Make sure the image you pushed is tagged to match (this uses :latest).
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent
export IMAGE_URI=$ECR_REPO:latest
export ROLE_ARN=<your-execution-role-arn>    # e.g. arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaAgentExecutionRole

RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$IMAGE_URI\"}}" \
  --role-arn "$ROLE_ARN" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --authorizer-configuration "{
    \"customJWTAuthorizer\": {
      \"discoveryUrl\": \"https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration\",
      \"allowedClients\": [\"${CLIENT_ID}\"]
    }
  }" \
  --request-header-configuration '{"requestHeaderAllowlist": ["Authorization", "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token"]}' \
  --region $AWS_REGION
```

> `update-agent-runtime` is a full PUT operation — any field you omit is reset,
> not preserved. So even though you configured the JWT authorizer via the
> console, you must re-supply the artifact, role, and network configuration here
> alongside the authorizer and header allowlist. Use the same `IMAGE_URI` and
> `ROLE_ARN` you deployed with (they may differ from the examples if you chose
> different ECR repo or role names). Note there is **no** `allowedAudience` —
> only `allowedClients`.

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

## Step 5 — Update the Agent Code to Read Identity from JWT

Copy the Module 07 agent files to `aria-agent/`:

```bash
cp modules/module-07-identity/agent.py aria-agent/agent.py
cp modules/module-07-identity/config.py aria-agent/config.py
cp modules/module-07-identity/requirements.txt aria-agent/requirements.txt
cp modules/module-07-identity/Dockerfile aria-agent/Dockerfile
cp -r modules/module-07-identity/identity aria-agent/
```

Verify:

```bash
ls aria-agent/identity/
# jwt.py

ls aria-agent/memory/
# session.py   (carried over from Module 06)
```

> The agent still uses Gateway tools (Module 05) and Memory (Module 06). Those
> files (`memory/`) and the `gateway_endpoint` SSM parameter are already in
> place — Module 07 only layers identity on top.

<details>
<summary>What changed in agent.py</summary>

The Module 07 agent replaces the `payload["customer_id"]` approach with JWT
claims extracted from the forwarded id-token header. Tools are still discovered
from the AgentCore Gateway via MCP (unchanged from Modules 05/06):

```python
# Module 06 — trust the payload
customer_id = payload.get("customer_id", "anonymous")

# Module 07 — trust the verified JWT
from identity.jwt import extract_identity
identity = extract_identity(context)
customer_id = identity.customer_id   # = custom:customer_id claim (C001)
customer_name = identity.name        # = name claim
customer_email = identity.email      # = email claim
```

The customer's `custom:customer_id` is also used as the `actor_id` for memory
scoping, so each authenticated customer gets their own memory namespace.

</details>

<details>
<summary>What identity/jwt.py does</summary>

`extract_identity` reads the id_token from the
`X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token` header (forwarded by the
Runtime), base64-decodes the JWT payload (no signature check — the Runtime
already validated the access token), and returns a typed `CustomerIdentity`:

```python
@dataclass
class CustomerIdentity:
    customer_id: str    # custom:customer_id claim — matches DynamoDB customerId (e.g. C001)
    name: str           # JWT name claim
    email: str          # JWT email claim
    raw_claims: dict    # full decoded claims for debugging

def extract_identity(context) -> CustomerIdentity:
    headers = getattr(context, "request_headers", {}) or {}
    id_token = (
        headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token")
        or headers.get("x-amzn-bedrock-agentcore-runtime-custom-id-token", "")
    )
    if not id_token:
        return ANONYMOUS
    # Decode without verification — Runtime already validated the access token
    claims = json.loads(base64.urlsafe_b64decode(id_token.split(".")[1] + "=="))
    return CustomerIdentity(
        # custom:customer_id is set to C001/C002/C003 at user creation
        # Falls back to sub (Cognito UUID) if the attribute is missing
        customer_id=claims.get("custom:customer_id") or claims.get("sub", "anonymous"),
        name=claims.get("name", ""),
        email=claims.get("email", ""),
        raw_claims=claims,
    )
```

</details>

---

## Step 6 — Rebuild the Agent and Deploy

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
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaAgentExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 07 — Identity" \
  --region $AWS_REGION
```

Wait for the runtime status to return to **Ready**.

---

## Step 7 — Update the Streamlit UI

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
- Every invocation sends `Authorization: Bearer <id_token>` directly over HTTPS

> **Why HTTPS instead of Boto3?**
> When a runtime is configured with a JWT authorizer, Boto3's
> `invoke_agent_runtime` cannot pass a Bearer token — it only supports SigV4
> signing. Invocations must be made via plain HTTPS to the AgentCore endpoint
> so the `Authorization` header can be included.

- The sidebar shows the logged-in customer's name and email from the token claims
- A **Sign out** button clears the token and redirects to Cognito's logout endpoint

The `ARIA_HARNESS_ARN`, `AWS_REGION`, and Cognito parameters are loaded from
SSM at startup — no hardcoding required.

</details>

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
3. Log in as `alice@example.com` / `ShopSmart1!`
4. You are redirected back to Streamlit — the sidebar now shows **Alice Johnson**
5. Send a message: `Hi!` — Aria should greet Alice by name immediately

> Customers log in with their **email address** (the Cognito sign-in
> identifier), not their customer ID. The `custom:customer_id` attribute
> (`C001`) is carried inside the token and used internally to look up orders.

### Verify the token is being validated

To confirm the Runtime rejects unauthenticated requests, invoke the HTTPS
endpoint without a Bearer token:

```bash
RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region us-east-1 \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeArn" \
  --output text)

ESCAPED_ARN=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$RUNTIME_ARN")

# No Authorization header → should return 401 Unauthorized
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/${ESCAPED_ARN}/invocations?qualifier=DEFAULT" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"hello"}'
```

> Note: you cannot test this with `aws bedrock-agentcore invoke-agent-runtime`
> (Boto3) — once the runtime uses a JWT authorizer, Boto3's SigV4 signing is
> rejected with an authorization-method-mismatch error, not a clean 401.

### Test all three customers

| Login (email) | Expected greeting |
|---|---|
| `alice@example.com` / `ShopSmart1!` | "Hi Alice! How can I help you?" |
| `bob@example.com` / `ShopSmart1!` | "Hi Bob! How can I help you?" |
| `carol@example.com` / `ShopSmart1!` | "Hi Carol! How can I help you?" |

---

<details>
<summary>Troubleshooting</summary>

**401 Unauthorized on all requests**

- Check the JWT authorizer discovery URL in the Runtime config — it must include
  `/.well-known/openid-configuration` at the end.
- Check that `allowedClients` matches the App Client ID exactly (copy-paste, no
  trailing spaces).

**`Claim 'aud' value mismatch with configuration`**

- The authorizer has `allowedAudience` set, but the Cognito access token has no
  `aud` claim. Remove `allowedAudience` and validate with `allowedClients` only
  (re-run the Step 3 CLI command).

**`Claim 'client_id' value mismatch`**

- The Streamlit UI is sending the id_token as the Bearer instead of the
  access_token. The access_token carries `client_id`; the id_token does not.
  Confirm the UI uses `access_token` for the `Authorization` header.

**Identity claims not reaching agent code (Aria doesn't know the name)**

- Confirm the `--request-header-configuration` includes both `Authorization`
  and `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token`. The console does not
  expose this — it must be set via CLI.
- Check CloudWatch logs for `extract_identity` — `customer_id=anonymous` means
  the id-token header arrived empty.

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
- How the request header allowlist works and why both the access token and id token are forwarded
- Why the access token is used for validation (has `client_id`) while the id token carries profile claims
- How to extract verified identity claims from the forwarded id token in agent code
- Why `custom:customer_id` is used as `actor_id` so it matches the DynamoDB customer records
- How the Streamlit authorization code flow works with Cognito Hosted UI
- The difference between inbound auth (who can call the agent) and outbound auth (what the agent can call)

</details>

---

## Next Step

Proceed to [Module 08 — Policy](../module-08-policy/README.md) where you will
add Cedar-based guardrails to control what Aria is allowed to do — and for whom.
