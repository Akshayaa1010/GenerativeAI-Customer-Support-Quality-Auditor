# 🚀 Production Deployment Guide

Follow this step-by-step guide to deploy the **GenerativeAI Customer Support Quality Auditor Pro** to production platforms such as **Railway.app**, **Render.com**, or **Hugging Face Spaces** using Docker.

---

## 1. Prerequisites
- Repository pushed to GitHub: `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`
- An active account on your deployment platform (e.g., Railway, Render, or Hugging Face)
- API Keys:
  - `GROQ_API_KEY`: Groq API key for Llama 3.3 70B & Whisper-v3
  - `PINECONE_API_KEY`: Pinecone API key for vector RAG policy retrieval

---

## 2. Deploying on Railway.app

1. Log in to [Railway.app](https://railway.app/).
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select the repository `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`.
4. Railway will automatically detect the `Dockerfile`.
5. Go to the **Variables** tab in your Railway dashboard and add:
   - `GROQ_API_KEY` = `your_groq_api_key`
   - `PINECONE_API_KEY` = `your_pinecone_api_key`
   - `FLASK_SECRET_KEY` = `your_random_secret_key` (optional but recommended)
6. Railway will build the container using `Dockerfile` and serve the app via **Gunicorn WSGI**.

---

## 3. Deploying on Render.com

1. Log in to [Render.com](https://render.com/).
2. Click **"New +"** -> **"Web Service"**.
3. Connect your GitHub repository.
4. Select **Environment**: `Docker`.
5. Under **Environment Variables**, add:
   - `GROQ_API_KEY`
   - `PINECONE_API_KEY`
   - `PORT` (Render sets `$PORT` automatically)
6. Click **"Create Web Service"**.

---

## 4. Container Strategy & Performance Benefits

We use a lightweight, production-optimized `Dockerfile` based on `python:3.10-slim` which:
- Pre-downloads the SpaCy NLP model (`en_core_web_sm`) during the build step.
- Runs the Flask application using **Gunicorn WSGI** with multiple workers and threads for concurrent requests.
- Uses dynamic `$PORT` binding (`0.0.0.0:${PORT:-7860}`) for universal compatibility across cloud hosts.

---

## 5. Persistent Storage & Production Database

Cloud containers use ephemeral storage. To preserve audit logs (`data/audit_results.csv`) and user accounts (`data/users.json`) across redeployments:
- **Persistent Volume**: Attach a persistent storage volume to `/app/data` in Railway/Render settings.
- **Production Storage**: For enterprise deployments, configure a managed database (PostgreSQL/MySQL) or object storage (S3) for audit logs.
