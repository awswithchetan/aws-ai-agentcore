# Building Production-ready AI Agents on AWS with Amazon Bedrock AgentCore

This repo is a part of my course on Udemy where I have explained the architecture in detail and demonstrated complete deployment process for building AI Agent from scratch.

**Course link** [Udemy | Build Production-Ready AI Agent on AWS with AgentCore](https://www.udemy.com/course/build-production-ready-ai-agent-on-aws/?referralCode=C3F97ED4D706F1112786)

<img width="1920" height="1080" alt="course-title-udemy-2" src="https://github.com/user-attachments/assets/fbbd3a0a-8738-4c97-8297-7ab1538699a8" />


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

<img width="1920" height="1080" alt="architecture-for-video" src="https://github.com/user-attachments/assets/296b293a-97b8-4f10-98fa-b3534611624e" />

---

## Course Modules

| Module | Topic | AgentCore Capability |
|--------|-------|---------------------|
| 00 | Prerequisites & Setup | — |
| 01 | AgentCore Platform Overview | All components — concept & video |
| 02 | Your First Agent | Strands agent (local) |
| 03 | Deploying Agents | Runtime |
| 04 | Knowledge Base | Bedrock Knowledge Base |
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
├── aria-agent/                 # Active/generated Runtime deployment workspace
│   ├── .dockerignore           # Shared container build exclusions
│   ├── memory/                 # Added by Module 06
│   ├── identity/               # Added by Module 07
│   ├── policies/               # Added by Module 08
│   ├── tools/                  # Added by Module 09
│   └── scripts/                # Deployment helper scripts
├── streamlit-ui/               # Chat UI
│   └── app.py
└── modules/                    # Step-by-step module guides
    ├── module-00-prerequisites/
    ├── module-01-platform-overview/
    ├── module-02-first-agent/
    ├── module-03-runtime/
    ├── module-04-knowledge-base/
    ├── ...
    └── module-10-cleanup/
```

---

## Prerequisites

The module folders are the source of truth for the progressive agent snapshots. `aria-agent/` is the active/generated deployment workspace: each Runtime module copies its `agent.py`, `config.py`, `requirements.txt`, and `Dockerfile` into that directory before building or packaging. Module 08 is policy-only and does not provide a new agent snapshot.

- AWS Account with appropriate permissions
- Python 3.11+
- AWS CLI v2
- Docker Desktop
- VS Code (recommended)

---

## Getting Started

Start with [Module 00 — Prerequisites & Setup](modules/module-00-prerequisites/README.md)

---

## AWS Services Used

- **Amazon Bedrock AgentCore** — Runtime, Gateway, Memory, Identity, Policy, and Browser
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
