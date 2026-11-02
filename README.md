# Call Quality Auditor

An admin dashboard for customer-support managers. Upload a recorded support
call, and the AI scores the employee against your company policy. The
dashboard shows each employee's scores, the rules they break most often, and
an AI-generated coaching plan for the team.

**Live app:** https://call-quality-auditor.onrender.com (admin login required).
On Render's free plan the app sleeps after 15 minutes without visitors, so the
first page load after a break can take up to a minute.

**Try it:** the [samples/](samples/) folder has seven recorded test calls,
each with the outcome it should get (PASS, WARN or FAIL).

**Full documentation:** [docs/Project_Documentation.pdf](docs/Project_Documentation.pdf)
covers the architecture, RAG, scoring, security, every bug fixed, a build-from-scratch
guide and deployment.

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
samples/                seven test calls (.wav) and their expected outcomes
docs/                   project documentation (PDF)
tests/                  unit tests (no network needed)
Dockerfile              production image (gunicorn)
render.yaml             Render deployment settings
cloudbuild.yaml         Google Cloud Run deployment (alternative)
```

## Services used

| Service | Used for | Free tier |
|---|---|---|
| [Groq](https://console.groq.com) | Whisper speech-to-text and the `openai/gpt-oss-120b` LLM | Yes |
| [Pinecone](https://www.pinecone.io) | Policy embeddings (`multilingual-e5-large`) and vector search | Yes |
| [Neon](https://neon.tech) | PostgreSQL database in production | Yes |
| [Render](https://render.com) | Hosting the Docker container | Yes |

## Run locally

Requires Python 3.12.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt     # app + test tools
python -m spacy download en_core_web_sm
copy .env.example .env          # then fill in the values
python app.py
```

Open http://127.0.0.1:7860 and sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`.
Without `DATABASE_URL`, audits are stored in a local SQLite file (`data/auditor.db`).

Run the tests:

```bash
python -m pytest
```

## Settings

| Variable | Required | Purpose |
|---|---|---|
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | yes | the single admin login |
| `FLASK_SECRET_KEY` | yes in production | signs the login cookie |
| `GROQ_API_KEY` | yes | transcription and AI scoring |
| `PINECONE_API_KEY` | recommended | policy retrieval; without it every rule is checked |
| `DATABASE_URL` | yes in production | PostgreSQL connection string (e.g. Neon) |
| `GROQ_LLM_MODEL`, `GROQ_WHISPER_MODEL` | no | override the default models |

## Deploy to Render (current hosting)

[render.yaml](render.yaml) describes the service: it builds the Dockerfile on the
free plan, checks `/healthz`, and generates `FLASK_SECRET_KEY`.

1. Create a free PostgreSQL database on [Neon](https://neon.tech) and copy its connection string.
2. On Render choose **New → Blueprint**, connect this GitHub repository and pick the
   branch named in `render.yaml`.
3. Enter `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `GROQ_API_KEY`, `PINECONE_API_KEY`
   and `DATABASE_URL` when asked, then click **Apply**.

Every push to that branch redeploys automatically. The app refuses to start in
production without `DATABASE_URL`, because the container's disk is wiped on restart.

## Deploy to Google Cloud Run (alternative)

1. Create a PostgreSQL database and copy its connection URL.
2. Create these secrets in Secret Manager: `DATABASE_URL`, `FLASK_SECRET_KEY`,
   `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `GROQ_API_KEY`, `PINECONE_API_KEY`.
3. Connect the repository to a Cloud Build trigger that uses `cloudbuild.yaml`.

## Known limitations

- Speaker labels (Agent / Customer) come from the LLM reading the text, not from
  the audio, so a line is occasionally attributed to the wrong speaker.
- Name redaction combines spaCy with context rules ("my name is …", "Mr. …",
  verification answers). Names mentioned in other ways can still slip through.
- Audits run in a background thread. If the server restarts mid-audit, that
  audit is marked failed after 30 minutes and must be uploaded again.
