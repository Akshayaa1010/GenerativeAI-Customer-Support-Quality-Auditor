# Call Quality Auditor

An admin dashboard for customer-support managers. Upload a recorded support
call, and the AI scores the employee against your company policy. The
dashboard shows each employee's scores, the rules they break most often, and
an AI-generated coaching plan for the team.

## How a call is audited

```
audio file
  → Groq Whisper            speech to text
  → PII redaction           names, phones, cards, Aadhaar, IFSC, emails removed
  → Groq LLM                label each line as Agent or Customer
  → RAG (Pinecone)          find the policy rules relevant to this call
  → Groq LLM                pass / fail / not applicable per rule, with evidence;
                            empathy and professionalism ratings
  → scoring (Python)        weighted score and PASS / WARN / FAIL outcome
  → database                shown on the dashboard
```

Personal data is redacted **before** any text is sent to an LLM.

### Scoring

The LLM only makes judgements. The numbers are calculated in
[backend/scoring.py](backend/scoring.py) using the weights in section 4 of
[data/policy.txt](data/policy.txt):

| Part | Weight | How it is calculated |
|---|---|---|
| Compliance | 40% | 100, or 0 if any zero-tolerance rule (section 3) was broken |
| Protocol | 30% | share of the other applicable rules that were followed |
| Soft skills | 30% | average of empathy and professionalism (0–100) |

Outcome: **FAIL** if a zero-tolerance rule was broken, **WARN** if any other
rule was broken, otherwise **PASS**.

### Policy retrieval (RAG)

[backend/rag.py](backend/rag.py) embeds every rule in `policy.txt` with
Pinecone's hosted `multilingual-e5-large` model and stores the vectors in a
Pinecone index. The index is created and filled automatically the first time
a call is audited, and refilled whenever `policy.txt` changes. For each call,
the transcript is split into windows of a few turns, and the closest rules to
each window are retrieved. Zero-tolerance rules are always checked. If
Pinecone is not configured, every rule is checked.

To change the policy, edit `data/policy.txt`. Rules are written as
`[Rule X.Y] Title` followed by their text. Rules in a section whose heading
contains "ZERO TOLERANCE" are treated as critical.

## Project structure

```
app.py                  Flask routes (pages + JSON API)
backend/
  config.py             settings read from the environment / .env
  policy.py             parses policy.txt into rules
  rag.py                Pinecone indexing and retrieval of relevant rules
  redaction.py          PII redaction
  llm.py                Groq client (Whisper + chat)
  scoring.py            speaker labelling, AI evaluation, score calculation, coaching plan
  pipeline.py           runs the audit steps in the background
  database.py           SQLite (local) / PostgreSQL (production)
frontend/
  templates/            login.html, dashboard.html
  static/               app.js, styles.css
data/policy.txt         the company policy the AI audits against
tests/                  unit tests (no network needed)
```

## Run locally

Requires Python 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m spacy download en_core_web_sm
copy .env.example .env          # then fill in the values
python app.py
```

Open http://127.0.0.1:7860 and sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.

Run the tests:

```bash
python -m pytest
```

## Deploy to Google Cloud Run

1. Create a PostgreSQL database (Cloud SQL, Neon, or Supabase) and copy its connection URL.
2. Create these secrets in Secret Manager: `DATABASE_URL`, `FLASK_SECRET_KEY`,
   `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `GROQ_API_KEY`, `PINECONE_API_KEY`.
3. Connect the repository to a Cloud Build trigger that uses `cloudbuild.yaml`.
   Each push to `main` builds the Docker image and deploys it.
