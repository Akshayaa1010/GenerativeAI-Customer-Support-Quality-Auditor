# 📊 Compliance Audit & Agent Performance Dashboard

A streamlined, AI-integrated dashboard for monitoring quality, compliance, and performance across customer service teams. This tool automates the auditing process for both **Audio Recordings** and **Email Threads**, providing actionable feedback for agent coaching.

---

## 🚀 Core Capabilities

### 🎙️ Audio Auditing
- **Fast Transcription**: Uses **Groq Whisper-v3** to convert audio to text in seconds.
- **Auto-Diarization**: The AI automatically distinguishes between 'Agent' and 'Customer' turns.
- **In-depth Scoring**: Analyzes every segment of the conversation for empathy and professionalism.

### 📧 Email Quality Analysis
- **Direct Extraction**: Securely pulls content from webmail (Gmail/Outlook) via a specialized browser bridge.
- **Smart Session Management**: Remembers your login state locally in `data/user_data` to minimize repetitive sign-ins.
- **Unified Compliance**: Applies the same high-standard policy checks to emails as used for audio calls.

### 🎯 Performance Tracking
- **Agent Matrix**: Categorizes team members into performance buckets (Stars, Robots, Charmers, Risks) based on emotional and professional metrics.
- **Automated Coaching**: Clusters common mistakes across the team to generate personalized development plans.
- **RAG-Based Privacy/Compliance**: Uses **Pinecone** to retrieve and apply your specific company policies to every audit.

---

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Dark-themed analytics UI)
- **AI Engine**: Groq (Llama-3 & Whisper-v3)
- **Vector Storage**: Pinecone (For RAG-based policy retrieval)
- **Automation**: Playwright (Browser bridge for email extraction)
- **Data Engine**: Pandas & Plotly (Metric processing and visualization)

---

## ⚙️ Quick Start

### 1. Installation
Requires **Python 3.10+**.

```bash
# Install dependencies
pip install -r requirements.txt

# Setup browser bridge
playwright install chromium
```

### 2. Configuration
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
```

### 3. Policy Setup
To use your own compliance rules, place them in `data/policy.txt` and run:
```bash
python backend/upload_policies.py
```

---

## 🖥️ Using the Dashboard

### Launching Locally
```bash
streamlit run frontend/dashboard.py
```

### Deployment
This project is optimized for deployment on **Railway.app** using the provided `Dockerfile`. This ensures that all dependencies, including Playwright for email extraction, are correctly configured.

1. Push your code to GitHub.
2. Connect your repository to Railway.
3. Add your environment variables (`GROQ_API_KEY`, `PINECONE_API_KEY`) in the Railway dashboard.

### Auditing Audio
1. Enter the agent's name in the sidebar.
2. Upload an **MP3** file.
3. Hit "Process & Analyze". The system handles transcription, labeling, and scoring automatically.

### Auditing Emails
1. Go to the **Email Analysis** page.
2. Click "Launch Email Browser" to open your mail client.
3. While viewing an email, click "Extract & Score from Browser" to run the audit.

---

## 📂 Project Layout

- `frontend/`: UI components and dashboard navigation.
- `backend/`: AI processing, scoring logic, and email extraction scripts.
- `data/`: Local storage for policies, uploads, and session data.
- `project_management/`: Agile tracking and team sheets.
- `requirements.txt`: Full list of project dependencies.

---

## 🔒 Security
- **Local Sessions**: Browser profile data is stored locally in `data/user_data/` and is never pushed to the repository.
- **Key Management**: Sensitivity is handled via environment variables (`.env`).
