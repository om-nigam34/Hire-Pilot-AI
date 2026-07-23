# HirePilot AI

**An AI-powered resume evaluation pipeline that scores resumes against job descriptions using semantic similarity and chained LLM reasoning.**

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Backend-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![LLM API](https://img.shields.io/badge/LLM_API-Inference-6366F1?style=flat-square)]()
[![SentenceTransformers](https://img.shields.io/badge/Embeddings-SentenceTransformers-FFD21E?style=flat-square)](https://www.sbert.net/)
[![SQLite](https://img.shields.io/badge/SQLite-Storage-07405E?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

---

## Overview

HirePilot AI takes a resume and a job description and returns a structured, explainable fit assessment — not a vague "looks good" chat response. It combines a deterministic embedding-based similarity score with a two-stage LLM reasoning pipeline: one pass evaluates the resume against the job description, and a second, chained pass generates concrete improvement suggestions based on that evaluation. Every session is persisted, so results are both reproducible and reviewable.

The project is under active development.

---

## Architecture

```
Resume -> PDF
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
SQLite Session Storage
     │
     ▼
JSON Response -> Frontend Dashboard
```

| Stage | Description |
|---|---|
| **Intake** | Resume PDF is parsed and text is extracted |
| **Similarity Scoring** | Resume and job description are embedded and compared via cosine similarity — a deterministic, reproducible score |
| **Evaluation (LLM Pass 1)** | An LLM call assesses resume-to-JD fit and produces a structured evaluation |
| **Improvement Generation (LLM Pass 2)** | A second LLM API call, conditioned on the first call's output, generates specific, actionable resume improvements |
| **Persistence** | Every session is saved to SQLite, giving users a full history of past evaluations |
| **Presentation** | Results are rendered on a dashboard with an animated score gauge and a session history sidebar |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask, Python 3.10 |
| AI / Inference | LLM API |
| Semantic Scoring | sentence-transformers |
| PDF Parsing | PyPDF2 / pdfplumber |
| Data Storage | SQLite |
| Frontend | Vanilla JavaScript, CSS |

---

## Design Rationale

**Why not just use a general-purpose chatbot?**

- **Consistency** — the same structured pipeline runs on every request, independent of how well a user happens to phrase a prompt
- **Hybrid scoring** — combines a deterministic embedding-similarity score with LLM judgment, rather than relying on model opinion alone
- **Persistence** — every evaluation is saved and retrievable, unlike a chat session that disappears on close
- **Purpose-built** — designed around a single, well-defined task rather than open-ended conversation
- **Cost-efficient inference** — built on a fast, low-cost LLM API

**On the architecture, specifically:** this is a **chained LLM pipeline** — two sequential LLM API calls, where the second is conditioned on the first's output — layered on top of a deterministic embedding-similarity score. It is not an autonomous multi-agent system, and it's described accurately here on purpose. The more defensible engineering story is in the details: fail-fast input validation, typed exception handling, and a hybrid scoring approach that pairs analytical and generative methods.

---

## Roadmap

- [ ] Public deployment
- [ ] Human-labeled evaluation set to establish a validated accuracy figure for the similarity scorer
- [ ] Authentication
- [ ] Expanded test coverage across utility modules

---

## License

All rights reserved. This code is publicly viewable for portfolio purposes; no license is granted for reuse, modification, or distribution at this time.

---

Built by [Om Nigam](https://github.com/om-nigam34)