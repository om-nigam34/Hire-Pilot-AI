# HirePilot AI

**An AI-powered resume evaluation platform that scores resumes against job descriptions using semantic similarity and a chained LLM pipeline — with accounts, saved history, and real authentication.**

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Werkzeug](https://img.shields.io/badge/Auth-Werkzeug-2F4F4F?style=flat-square&logo=python&logoColor=white)](https://werkzeug.palletsprojects.com/)
[![LLM API](https://img.shields.io/badge/LLM_API-Inference-6366F1?style=flat-square)]()
[![SentenceTransformers](https://img.shields.io/badge/Embeddings-SentenceTransformers-FFD21E?style=flat-square)](https://www.sbert.net/)
[![SQLite](https://img.shields.io/badge/SQLite-Storage-07405E?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Engineering Highlights](#engineering-highlights)
- [Tech Stack](#tech-stack)
- [Design Rationale](#design-rationale)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

HirePilot AI takes a resume and a job description and returns a structured, explainable fit assessment — not a vague "looks good" chat response. Every user has their own account, so results are private, saved, and reviewable across sessions instead of disappearing when the tab closes.

Under the hood, it combines a deterministic embedding-based similarity score with a two-stage LLM reasoning pipeline: one pass evaluates the resume against the job description, and a second, chained pass generates concrete improvement suggestions based on that evaluation.

---

## Architecture

```
Login / Signup
     │
     ▼
Resume PDF + Job Description
     │
     ▼
Text Extraction
     │
     ▼
Embedding + Cosine Similarity
     │
     ▼
LLM Call -1 —> Evaluate
     │
     ▼
LLM Call -2 —> Generate Improvements
     │
     ▼
SQLite Session Storage (scoped to user)
     │
     ▼
JSON Response -> Dashboard
```

| Stage | Description |
|---|---|
| **Authentication** | Every route past the landing page is gated behind login; sessions are re-verified against the database on each request, not just trusted from the cookie |
| **Intake** | Resume PDF is parsed and text is extracted |
| **Similarity Scoring** | Resume and job description are embedded and compared via cosine similarity — a deterministic, reproducible score |
| **Evaluation (LLM Pass 1)** | An LLM call assesses resume-to-JD fit and produces a structured evaluation |
| **Improvement Generation (LLM Pass 2)** | A second LLM API call, conditioned on the first call's output, generates specific, actionable resume improvements |
| **Persistence** | Every session is saved to SQLite, scoped to the logged-in user, giving each account its own history of past evaluations |
| **Presentation** | Results are rendered on a dashboard with an animated score gauge and a per-user session history sidebar |

---

## Engineering Highlights

- **Password hashing, not storage.** Passwords are hashed with Werkzeug's `generate_password_hash` before they ever touch the database; login checks a hash comparison, never a plaintext password.
- **Sessions are re-verified, not just trusted.** Every request checks the session's user ID against the database instead of assuming a cookie means a valid account — this caught a real bug where a stale cookie from a wiped local DB crashed the app.
- **IDOR fix on session history.** Every session lookup is scoped by `user_id` at the query level, so no account can read another account's history by guessing or incrementing an ID.
- **19-check automated test suite.** Covers signup, login, logout, duplicate account rejection, IDOR prevention, and the stale-session regression case above.
- **Chained, not autonomous.** The improvement-generation call is conditioned on the evaluation call's structured output — two sequential LLM calls, not independent agents.
- **Typed exceptions, mapped to real status codes.** `ModelUnavailableError`, `PDFExtractionError`, `LLMClientError`, and `LLMResponseError` each map to a distinct HTTP response instead of one generic 500.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask, Python |
| Auth | Werkzeug (password hashing), Flask sessions |
| AI / Inference | LLM API |
| Semantic Scoring | sentence-transformers |
| PDF Parsing | pypdf |
| Data Storage | SQLite |
| Frontend | Vanilla JavaScript, CSS |
| Deployment | Gunicorn, Render |

---

## Design Rationale

**Why not just use a general-purpose chatbot?**

- **Consistency** — the same structured pipeline runs on every request, independent of how well a user happens to phrase a prompt
- **Hybrid scoring** — combines a deterministic embedding-similarity score with LLM judgment, rather than relying on model opinion alone
- **Persistence** — every evaluation is saved per account and retrievable, unlike a chat session that disappears on close
- **Purpose-built** — designed around a single, well-defined task rather than open-ended conversation
- **Cost-efficient inference** — built on a fast, low-cost LLM API

**On the architecture, specifically:** this is a **chained LLM pipeline** — two sequential LLM API calls, where the second is conditioned on the first's output — layered on top of a deterministic embedding-similarity score. It is not an autonomous multi-agent system, and it's described accurately here on purpose. The more defensible engineering story is in the details: fail-fast input validation, typed exception handling, per-user data isolation, and a hybrid scoring approach that pairs analytical and generative methods.

---

## Roadmap

- [x] Authentication — accounts, hashed passwords, per-user session scoping
- [x] Automated test suite — 19 checks across the auth flow
- [ ] Public deployment on Render
- [ ] Human-labeled evaluation set to establish a validated accuracy figure for the similarity scorer
- [ ] Rate limiting on the analysis endpoint
- [ ] Deeper resume upload validation

---

## License

All rights reserved. This code is publicly viewable for portfolio purposes; no license is granted for reuse, modification, or distribution at this time.

---

Built by [Om Nigam](https://github.com/om-nigam34)