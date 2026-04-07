# Doubts & Open Questions

## 1. System Design Concern — Global Search vs. User-Intent-Driven Search

### The Problem

The current framing of the assignment implies building a system that ingests **all trades globally** across every market, and then runs insider detection across that entire dataset.

This approach raises a fundamental design question:

> **Who is the actual end user of this system, and what are they trying to find out?**

A global ingestion pipeline makes sense for a background monitoring system. But it does not make sense if the user's intent is narrow and specific — for example:

> *"I want to know if there has been any insider trading on the market: Will Spain win the FIFA World Cup?"*

In this case, the user has **one market in mind**. They should not need to wait for the system to scan millions of trades across thousands of unrelated markets just to get an answer about that one.

---

### The Core Doubt

Should the system be designed **globally-first** (ingest everything, detect everywhere), or should it be designed **intent-first** (user specifies a market or trade, system runs detection only on that scope)?

---

### Proposed Clarification

The system should support at least two modes:

**Mode 1 — Targeted Query (User-Driven)**
The user provides a specific market, wallet, or transaction. The system fetches and scores only the data relevant to that input. This is fast, lightweight, and directly answers the user's question.

Example user intent:
- "Was there insider activity on the Spain FIFA World Cup market?"
- "Is this wallet address suspicious?"
- "Did anyone have advance knowledge before this specific trade resolved?"

**Mode 2 — Global Monitoring (Background Pipeline)**
A continuously running indexer that ingests all `OrderFilled` events, stores them in a database, and periodically scores all wallets for insider signals. This is useful for surveillance dashboards or alerting systems.

---

### Why This Distinction Matters

Building only a global pipeline without a targeted query interface means:

- The system is slow to answer simple, specific questions
- It requires a fully populated database before it can return any useful result
- It does not serve the most natural user workflow, which is: *"I heard something about this market — let me quickly check if it looks suspicious"*

The better architecture likely combines both: a targeted query layer for immediate answers, backed by an optional global index for broader pattern detection.

---

*Logged for clarification before finalising system architecture.*

---

## Quick Questions — Copy-Paste Ready

1. Should the system support a targeted query mode where a user can check insider activity on just one specific market, or is the expectation always a global scan across all markets?

2. Who is the primary user of this system — a background monitoring pipeline, or someone actively investigating a specific trade or market in real time?

3. Should the insider detection be triggered on-demand (user searches a market/wallet) or should it run continuously as a scheduled job across all trades?

4. For the scoring algorithm, are the 5 signals (entry timing, trade concentration, wallet age, size, markets traded) equally weighted, or is there a preferred weighting we should start with?

5. For the USDC.e deposit indexing, do we only need the first-ever deposit per wallet, or all deposits over time?
