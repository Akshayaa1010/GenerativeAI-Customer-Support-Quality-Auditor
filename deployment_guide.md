# 🚀 Split Deployment Guide (Netlify / Vercel + Render)

Follow this step-by-step guide to deploy the **GenerativeAI Customer Support Quality Auditor Pro** using a decoupled architecture:
- **Backend**: Hosted on **Render.com** (Flask API + Gunicorn WSGI + Docker)
- **Frontend**: Hosted on **Vercel** or **Netlify** (Vanilla JS/CSS + Reverse Proxy)

---

## 📋 Prerequisites
- Repository pushed to GitHub: `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`
- API Keys:
  - `GROQ_API_KEY`: Groq API key for Llama 3.3 70B & Whisper-v3
  - `PINECONE_API_KEY`: Pinecone API key for vector RAG policy retrieval

---

## ⚙️ Step 1: Deploy Backend on Render.com

1. Log in to [Render.com](https://render.com/).
2. Click **"New +"** -> **"Web Service"** (or use the **Blueprint** option with `render.yaml`).
3. Connect your GitHub repository `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`.
4. Choose **Environment**: `Docker` (or select `render.yaml` for automatic setup).
5. In the **Environment Variables** section, set:
   - `GROQ_API_KEY` = `your_groq_api_key`
   - `PINECONE_API_KEY` = `your_pinecone_api_key`
   - `FLASK_SECRET_KEY` = `a_random_secure_secret_key`
6. Click **"Create Web Service"**.
7. Once Render builds and deploys your service, copy your Render URL (e.g. `https://compliance-auditor-backend.onrender.com`).

---

## 📐 Step 2: Deploy Frontend on Vercel

1. Log in to [Vercel.com](https://vercel.com/).
2. Click **"Add New..."** -> **"Project"**.
3. Import your GitHub repository `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`.
4. Update `vercel.json` in your repository replacing `https://your-backend.onrender.com` with your actual Render URL from Step 1:
   ```json
   {
     "version": 2,
     "rewrites": [
       { "source": "/api/:path*", "destination": "https://YOUR_BACKEND.onrender.com/api/:path*" },
       { "source": "/register", "destination": "https://YOUR_BACKEND.onrender.com/register" },
       { "source": "/login", "destination": "https://YOUR_BACKEND.onrender.com/login" },
       { "source": "/logout", "destination": "https://YOUR_BACKEND.onrender.com/logout" }
     ]
   }
   ```
5. Click **"Deploy"**. Vercel will serve your static frontend assets and seamlessly proxy `/api/*` requests to Render!

---

## 🌐 Step 3: Deploy Frontend on Netlify (Alternative)

1. Log in to [Netlify.com](https://netlify.com/).
2. Click **"Add new site"** -> **"Import an existing project"**.
3. Select **GitHub** and choose `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`.
4. Update `netlify.toml` in your repository replacing `https://your-backend.onrender.com` with your actual Render URL:
   ```toml
   [build]
     publish = "frontend"

   [[redirects]]
     from = "/api/*"
     to = "https://YOUR_BACKEND.onrender.com/api/:splat"
     status = 200
     force = true
   ```
5. Click **"Deploy Site"**. Netlify will host your frontend and proxy backend API routes to Render with zero CORS issues!

---

## 💾 Persistent Storage

Render containers use ephemeral storage. To persist audit logs (`data/audit_results.csv`) and user databases (`data/users.json`) across redeployments:
- Attach a **Persistent Disk** on Render mounted at `/app/data`.
