# Module 03 — Knowledge Base

In this module you will create the **ShopSmart Knowledge Base** — a Bedrock-managed vector store that gives Aria access to ShopSmart's official content. This is persistent infrastructure used by Aria throughout the rest of the course.

Instead of hardcoding FAQ content into the system prompt, Aria retrieves relevant information dynamically from the Knowledge Base. This is how production support agents actually work — content lives in documents, not in prompts.

---

## What You Will Build

```
S3 Bucket (shopsmart-knowledge-base)
└── Documents
    ├── return-policy.md
    ├── shipping-info.md
    ├── payment-methods.md
    ├── store-hours-and-support.md
    └── general-faq.md
        ↓
Bedrock Knowledge Base
└── Vector store (Amazon OpenSearch Serverless)
    └── Aria retrieves relevant chunks at query time
```

---

## Knowledge Base Documents

The documents are already in the repo at `shopsmart-backend/knowledge-base/`. You will upload these to S3 in Step 2.

| File | Content |
|------|---------|
| `return-policy.md` | Return windows, conditions, process, refund timelines |
| `shipping-info.md` | Domestic/international shipping options, tracking, restrictions |
| `payment-methods.md` | Accepted cards, wallets, BNPL, gift cards, security |
| `store-hours-and-support.md` | Support channels, hours, escalation |
| `general-faq.md` | Orders, account, products, pricing, loyalty, privacy |

---

## Step 1 — Create S3 Bucket

### Via AWS Console

1. Go to **AWS Console → S3 → Create bucket**
2. Configure:
   - **Bucket name**: `shopsmart-knowledge-base-<your-account-id>` *(must be globally unique)*
   - **Region**: `us-east-1`
   - **Block all public access**: enabled (default)
   - All other settings: leave as default
3. Click **Create bucket**

### Via CLI (Optional)

```bash
# Replace <your-account-id> with your actual AWS account ID
aws s3 mb s3://shopsmart-knowledge-base-<your-account-id> --region us-east-1
```

---

## Step 2 — Upload Knowledge Base Documents

### Via AWS Console

1. Open your newly created S3 bucket
2. Click **Upload → Add files**
3. Select all 5 files from `shopsmart-backend/knowledge-base/` in the repo
4. Click **Upload**

### Via CLI (Optional)

```bash
# From the repo root
aws s3 cp shopsmart-backend/knowledge-base/ \
  s3://shopsmart-knowledge-base-<your-account-id>/ \
  --recursive
```

Verify the upload:
```bash
aws s3 ls s3://shopsmart-knowledge-base-<your-account-id>/
```

---

## Step 3 — Create the Knowledge Base

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → Knowledge bases → Create knowledge base**
2. **Knowledge base details**:
   - **Name**: `shopsmart-kb`
   - **Description**: ShopSmart customer support knowledge base
   - **IAM role**: Create and use a new service role (let AWS create it automatically)
3. Click **Next**

4. **Set up data source**:
   - **Data source name**: `shopsmart-docs`
   - **Data source**: Amazon S3
   - **S3 URI**: `s3://shopsmart-knowledge-base-<your-account-id>/`
5. Click **Next**

6. **Configure vector store**:
   - **Embeddings model**: Titan Text Embeddings V2
   - **Vector store**: Amazon OpenSearch Serverless (Quick create — AWS creates it automatically)
7. Click **Next**

8. Review and click **Create knowledge base**

> Creation takes **3–5 minutes**. Wait until status shows **Available** before proceeding.

9. Note down the **Knowledge Base ID** — you will need it in Module 04 when attaching to Aria's Harness and Runtime.

---

## Step 4 — Sync the Data Source

After the Knowledge Base is created, you need to sync it to index the documents:

1. Open `shopsmart-kb` in the Bedrock console
2. Under **Data sources**, select `shopsmart-docs`
3. Click **Sync**
4. Wait until sync status shows **Available** (takes ~1 minute for 5 small files)

> Every time you update the documents in S3, you need to re-sync the data source for the changes to take effect.

---

## Step 5 — Test the Knowledge Base

Test that the Knowledge Base retrieves content correctly before connecting it to Aria.

### Via AWS Console

1. In the Knowledge Base detail page, click **Test knowledge base**
2. Try these test queries:
   - `What is the return window for electronics?`
   - `How much does express shipping cost?`
   - `What payment methods are accepted?`
3. You should see relevant document chunks returned with source attribution

The retrieved chunks are what Aria will use to formulate her answers.

---

## Step 6 — Note Down the Knowledge Base Details

Save these values — you will use them in Module 04:

```
Knowledge Base ID:  kb-XXXXXXXXXX
S3 Bucket:          s3://shopsmart-knowledge-base-<your-account-id>/
Region:             us-east-1
```

You can find the Knowledge Base ID on the knowledge base detail page in the Bedrock console.

---

## How the Knowledge Base Integrates with Aria

When a customer asks Aria a question:

```
Customer: "Can I return a jacket I bought 3 weeks ago?"
    ↓
Aria retrieves relevant chunks from Knowledge Base
    → return-policy.md: "Standard items: 30 days from delivery"
    → return-policy.md: "Items must be in original condition with all tags attached"
    ↓
Aria uses retrieved context to formulate a precise, accurate answer
    → "Yes, you're within the 30-day return window. The jacket needs to be
       in original condition with tags attached. Would you like me to
       initiate the return for you?"
```

Aria never makes up policy details — she retrieves them from the official documents.

---

## What You Learned

- How to create an S3 bucket as a document store
- How to create a Bedrock Knowledge Base with OpenSearch Serverless vector store
- How to sync documents and test retrieval
- How retrieval-augmented generation (RAG) works in the context of an agent

---

## Next Step

Proceed to [Module 04 — Runtime](../module-04-runtime/README.md) where you will build the full Aria agent, attach the Knowledge Base, and start evolving it with real capabilities.
