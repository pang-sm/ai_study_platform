# Product

<!-- impeccable:product-schema 1 -->

> 唯一产品 / 架构权威见 [`ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`](./ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md)。
> 本文件是给设计工具使用的产品摘要，从属于 SSOT；冲突时 SSOT wins。

## Platform

web

## Users

University learners who need a clear, reliable place to begin and continue structured learning
across three learning spaces: course learning, computer-science postgraduate exam 11408, and
programming practice.

## Product Purpose

智学AI helps learners turn difficult material into an ordered learning path, from the first entry
point through a focused learning task.

## Positioning

An academic study journal rather than a generic learning dashboard: the product anchors learning
in a visible curriculum structure and a concrete next step.

## Capabilities and Constraints

React and Vite frontend; FastAPI backend; authenticated data uses a server-issued HTTP-only session
cookie. Authentication must use the existing `/login`, `/register`, and `/me` contracts with
credentialed browser requests. No client token storage or authentication bypass is permitted.

Scientific components are **not** productized: all 13 are `RUNTIME_ONLY`, `SHADOW = 0 / ADVISORY = 0
/ ACTIVE = 0`. The UI must not expose any scientific component or invented learner state.

## Brand Commitments

ZHIXUE Academic Study Journal; Brand V2 is authoritative. Desktop uses the split brand system, while
mobile uses the Icon Only brand asset. Deep navy, academic ivory, restrained editorial typography,
and subtle knowledge-grid structure are established visual commitments.

## Evidence on Hand

Brand V2 assets under `frontend/public/brand/zhixue-v2/` and design references under `reference/`
(`reference/LOGO/`, `reference/PAGE/`, `reference/UI/` — protected, do not modify).

The new frontend is `NOT_STARTED`: `frontend/` currently contains only a Clean-Slate shell and the
home page. Older homepage / exam-world / workspace implementations were removed and **must not be
restored or copied** (SSOT §3.2 / §38).

## Product Principles

- Start with an understandable next action.
- Preserve real backend truth over static or simulated learning data.
- Keep dense academic material calm, legible, and navigable.
- Treat authentication as a trustworthy entry desk, not a marketing interruption.
