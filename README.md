# Building Production-Grade AI Agents with Amazon Bedrock AgentCore

## Course Overview

A hands-on course covering all major Amazon Bedrock AgentCore capabilities by building **Aria** — a production-grade AI customer support agent for a fictional retail company called **ShopSmart**.

Each module adds a new capability to Aria, so by the end of the course you have one complete, production-ready agent built incrementally — not a collection of isolated demos.

**Author**: [Chetan Agrawal](https://in.linkedin.com/in/chetan-agrawal-30107310)  
**Website**: [www.awswithchetan.com](https://www.awswithchetan.com)

---

## What You Will Build

**Aria** — ShopSmart's AI Customer Support Agent that can:
- Greet customers by name after login (Cognito authentication)
- Pull up open orders automatically — no order ID needed
- Check order status and delivery estimates
- Initiate returns and calculate refund amounts
- Search the product catalog
- Remember customers across sessions
- Check live carrier tracking pages

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Chat UI                     │
│              (Cognito login → JWT token)                 │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Amazon Bedrock AgentCore                    │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌─────────────┐  │
│  │ Runtime  │ │Gateway │ │  Memory  │ │  Identity   │  │
│  └──────────┘ └────────┘ └──────────┘ └─────────────┘  │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  Policy  │ │ Browser│ │  Gateway │ │             │  │
│  │          │ │        │ │           │ │             │  │
│  └──────────┘ └────────┘ └──────────┘ └─────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               ShopSmart Backend                          │
│  ┌──────────────────┐   ┌──────────────────────────┐    │
│  │   API Gateway    │   │      Cognito User Pool    │    │
│  └────────┬─────────┘   └──────────────────────────┘    │
│           │                                              │
│  ┌────────▼─────────────────────────────────────────┐   │
│  │              Lambda Functions                     │   │
│  │  get_order  list_orders  get_product  search      │   │
│  │  products   submit_request                        │   │
│  └────────┬─────────────────────────────────────────┘   │
│           │                                              │
│  ┌────────▼──────────┐   ┌──────────────────────────┐   │
│  │     DynamoDB      │   │            S3             │   │
│  │  orders-table     │   │  product-images-bucket    │   │
│  │  products-table   │   │  return-labels-bucket     │   │
│  └───────────────────┘   └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Course Modules

| Module | Topic | AgentCore Capability |
|--------|-------|---------------------|
| 00 | Prerequisites & Setup | — |
| 01 | AgentCore Platform Overview | All components — video only |
| 02 | Your First Agent | Harness |
| 03 | Knowledge Base | Bedrock Knowledge Base |
| 04 | Deploying Agents | Runtime |
| 05 | Connecting Real Tools | Gateway |
| 06 | Stateful Agents | Memory |
| 07 | Authentication | Identity |
| 08 | Guardrails & Governance | Policy |
| 09 | Browser Automation | Browser |
| 10 | Cleanup | — |

```
aws-ai-agentcore/
├── shopsmart-backend/          # Backend infrastructure
│   ├── cloudformation/         # CloudFormation templates
│   ├── lambdas/                # Lambda function code
│   ├── knowledge-base/         # ShopSmart FAQ documents
│   │   ├── return-policy.md
│   │   ├── shipping-info.md
│   │   ├── payment-methods.md
│   │   ├── store-hours-and-support.md
│   │   └── general-faq.md
│   └── seed_data.py            # DynamoDB seed script
├── aria-agent/                 # AgentCore agent code
│   ├── agent.py                # Main agent code
│   ├── agentcore.yaml          # Agent configuration
│   ├── tools/                  # Tool definitions
│   ├── policies/               # Cedar policy files
│   └── requirements.txt
├── streamlit-ui/               # Chat UI
│   └── app.py
└── modules/                    # Step-by-step module guides
    ├── module-00-prerequisites/
    ├── module-02-harness/
    ├── module-03-knowledge-base/
    ├── module-04-runtime/
    ├── ...
    └── module-10-cleanup/
```

---

## Prerequisites

- AWS Account with appropriate permissions
- Python 3.11+
- AWS CLI v2
- Docker Desktop
- AgentCore CLI (`pip install amazon-bedrock-agentcore-cli`)
- VS Code (recommended)

---

## Getting Started

Start with [Module 00 — Prerequisites & Setup](modules/module-00-prerequisites/README.md)

---

## AWS Services Used

- **Amazon Bedrock AgentCore** — Runtime, Harness, Gateway, Memory, Identity, Policy, and Browser
- **Amazon Cognito** — Customer authentication
- **AWS Lambda** — Tool backends
- **Amazon DynamoDB** — Orders and products data
- **Amazon API Gateway** — REST API for Lambda functions
- **Amazon S3** — Product images, return labels
- **Amazon CloudWatch** — Logs and traces
- **Amazon ECR** — Agent container registry


---

## Cleanup

When you finish the course, follow [Module 10 — Cleanup](modules/module-10-cleanup/README.md)
to remove the CloudFormation stacks and the remaining AgentCore, Cognito, S3,
ECR, SSM, IAM, and CloudWatch resources created during the exercises.
