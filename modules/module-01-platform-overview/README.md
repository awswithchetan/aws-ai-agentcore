# Module 01 — AgentCore Platform Overview

**Course link** [Udemy | Build Production-Ready AI Agent on AWS with AgentCore](https://www.udemy.com/course/build-production-ready-ai-agent-on-aws/?referralCode=C3F97ED4D706F1112786)

This module is a conceptual walkthrough of the **Amazon Bedrock AgentCore**
platform. There are no hands-on steps and nothing to deploy — it sets the
mental model for everything you build in the rest of the course.

> This module accompanies a video overview. Use this page as the written
> companion and reference.

---

## Why AgentCore

Getting an AI agent to *work* on your laptop is relatively easy but getting one to run reliably in production is the hard part:
hosting and scaling it, connecting it to real tools securely, giving it memory,
authenticating users, enforcing guardrails, and observing what it does.

Amazon Bedrock AgentCore is a set of managed building blocks that handle exactly
these production concerns, so you can focus on your agent's behavior rather than
the surrounding infrastructure. Importantly, the pieces are **modular** — you
adopt only the capabilities you need, and they work with any agent framework
(this course uses Strands).

---

## The capabilities you will use

Each capability below maps to a later module. Aria — ShopSmart's support agent —
gains one of these in each step, so by the end you've assembled a complete,
production-grade agent.

| Capability | What it provides | Module |
|------------|------------------|:------:|
| **Runtime** | Managed, scalable hosting for your agent, with sessions and observability | 03 |
| **Knowledge Base** | Grounds the agent in your own documents through retrieval | 04 |
| **Gateway** | Turns existing REST APIs into secure tools the agent can call (via MCP) | 05 |
| **Memory** | Lets the agent remember users and context across sessions | 06 |
| **Identity** | Authenticates users and passes verified identity to the agent | 07 |
| **Policy** | Enforces guardrails and access rules on what the agent may do | 08 |
| **Browser** | Lets the agent operate real websites that have no API | 09 |

---

## The Architecture that you are going to build in this course
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/fa4a86be-0be4-4043-8f05-4203e4ac4ad4" />


## How the course is structured

The course builds **one** agent incrementally. Rather than a collection of
isolated demos, every module adds a single capability to the same agent, Aria:

```
Module 02  Local agent (simulated tools, inline knowledge)
Module 03  + Runtime               (deployed, scalable hosting)
Module 04  + Knowledge Base        (real, searchable grounding)
Module 05  + Gateway               (real tools via APIs)
Module 06  + Memory                (remembers customers)
Module 07  + Identity              (authenticated users)
Module 08  + Policy                (enforced guardrails)
Module 09  + Browser               (live carrier tracking)
Module 10  Cleanup
```

In Module 02 several pieces are deliberately *simulated* — hardcoded tools,
inline FAQ, policy written as prompt text. Each later module replaces one of
those simulated pieces with the real, managed AgentCore capability above. Keep
that "simulate now, make it real later" idea in mind as you go.

---

## Next Step

With the platform model in mind, build your first agent and run it locally.

Proceed to [Module 02 — Your First Agent](../module-02-first-agent/README.md).
