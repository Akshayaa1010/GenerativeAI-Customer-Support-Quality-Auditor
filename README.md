# 📊 Quality Compliance Auditor Pro

A full-stack, AI-driven **Customer Support Quality & Compliance Auditor**. Built with Python (Flask), Groq (Llama-3.3 70B & Whisper-v3), Pinecone Vector Database (RAG), SpaCy NLP, and a modern Vanilla CSS/JS Glassmorphism UI.

The platform automates quality scoring, empathy & professionalism evaluation, PII masking, and compliance policy verification across both **Call Audio Recordings** and **Email Support Threads**.

---

## ✨ Key Features

### 🔐 Multi-Tenant User Authentication & Organization Isolation
- **Self-Service Registration**: Users can register directly from the login interface with their Username, Password, and Organization Name.
- **Tenant Data Isolation**: Audits, performance leaderboards, team analytics, agent deep-dives, and CSV/PDF downloads are strictly isolated by the logged-in user's Organization.
- **Secure Hashing**: User passwords are saved with SHA-256 encryption in local user storage (`data/users.json`).

### 🌓 Dark Mode & Light Mode Theme Switcher
- **Instant Theme Toggle**: Switch seamlessly between Dark Mode and Light Mode from either the Login Page or Dashboard header.
- **Zero-Flash Persistence**: User theme preferences are automatically saved in `localStorage` and applied before rendering.

### 📧 IMAP Email Extractor & AI Compliance Auditor
- **IMAP Server Integration**: Directly retrieve customer support emails from IMAP mail servers (Gmail, Outlook, etc.).
- **Manual Email Audit**: Instant evaluation of pasted email content.
- **RAG Policy Verification**: Scores empathy, professionalism, and policy compliance using Groq Llama-3.3 70B and Pinecone vector search.

### 🎙️ Audio Call Auditing & PII Redaction
- **Groq Whisper-v3 Transcription**: Fast, accurate speech-to-text conversion for call audio recordings.
- **Dialogue Diarization**: Automatic turn-by-turn labeling between `Agent` and `Customer`.
- **SpaCy PII Masking**: Detects and redacts sensitive PII (names, Aadhaar numbers, phone numbers, card numbers, emails) prior to audit logging.

### 📈 Interactive Analytics & Coaching Roadmap
- **ApexCharts Dashboard**: Real-time team averages, top policy violation frequencies, and agent performance comparisons.
- **AI Coaching Roadmap**: Clusters team-wide mistakes into structured training modules exportable as PDF reports.
- **Data Exporting**: Download organization-isolated audit logs in CSV format or formatted PDF summary reports.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, Flask, Gunicorn WSGI Server, Pandas, SpaCy, FPDF2
- **AI Engine**: Groq (Llama-3.3-70b-versatile & Whisper-v3)
- **Vector Search (RAG)**: Pinecone, LangChain
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism Design System), JavaScript (ES6+), Lucide Icons, ApexCharts
- **Email Extraction**: Python `imaplib` SSL client & BeautifulSoup4

---

## 🚀 Quick Start

### 1. Prerequisites & Installation

Clone the repository and install dependencies:

```bash
# Install required Python dependencies
pip install -r requirements.txt

# Download SpaCy English NLP model for PII redaction
python -m spacy download en_core_web_sm
```

### 2. Environment Configuration

Create a `.env` file in the project root directory:

```env
# Core API Keys
GROQ_API_KEY=your_groq_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here

# (Optional) Default Admin Credentials
AUTH_USERNAME=admin
AUTH_PASSWORD=admin123

# (Optional) IMAP Email Extraction Credentials
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_EMAIL=your_support_email@gmail.com
IMAP_PASSWORD=your_app_password
```

### 3. Running Locally

Start the Flask development server:

```bash
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:7860](http://127.0.0.1:7860)**

---

## 🐳 Docker Containerization & Deployment

### Running with Docker Locally

Build and start the container using the included `Dockerfile`:

```bash
# Build Docker Image
docker build -t compliance-auditor-pro .

# Run Docker Container
docker run -p 7860:7860 --env-file .env compliance-auditor-pro
```

### Deploying to Cloud Hosting (Railway / Render / Hugging Face Spaces)

1. Push your repository to GitHub.
2. Link the repository to your hosting provider (e.g., Railway or Render).
3. Add environment variables (`GROQ_API_KEY`, `PINECONE_API_KEY`, etc.) in your provider's project dashboard.
4. The deployment will automatically build using the `Dockerfile` and serve the application via **Gunicorn WSGI**.

---

## 📂 Project Structure

```
.
├── app.py                      # Main Flask application & REST endpoints
├── backend/                    # Core AI & auditing backend modules
│   ├── clean_transcript.py     # Diarization & speaker turn labeling
│   ├── extract_emails.py       # IMAP email extraction engine
│   ├── pipeline.py             # Audio-to-audit orchestration pipeline
│   ├── rag_compliance.py       # Pinecone vector RAG policy retriever
│   ├── redaction.py            # SpaCy PII masking & regex sanitizer
│   ├── scoring_engine.py       # Groq Llama-3 scoring & audit persistence
│   ├── transcribe.py           # Groq Whisper-v3 audio transcription engine
│   ├── upload_policies.py     # Script to upload policy rules to Pinecone
│   └── test_redaction.py       # Test suite for PII redaction rules
├── frontend/                   # Single-page web application frontend
│   ├── static/                 # Static web assets
│   │   ├── css/styles.css      # CSS design system & light/dark theme tokens
│   │   └── js/app.js           # Single-page app router, ApexCharts & theme toggler
│   └── templates/              # Jinja2 HTML templates
│       ├── dashboard.html      # Main compliance auditing dashboard
│       └── login.html          # Authentication & user registration view
├── data/                       # Storage directory for audit logs & user DB
├── Dockerfile                  # Production Docker container configuration
├── .dockerignore               # Container build exclusion rules
├── deployment_guide.md         # Production deployment instructions
└── requirements.txt            # Python package dependencies
```

---

## 🔒 Security & Data Privacy

- **PII Masking**: Sensitive customer PII is automatically redacted before audit results are saved.
- **Encrypted Password Storage**: User passwords are saved with SHA-256 hashing.
- **Multi-Tenant Boundaries**: Session-based organization filtering prevents cross-tenant data leakage.
