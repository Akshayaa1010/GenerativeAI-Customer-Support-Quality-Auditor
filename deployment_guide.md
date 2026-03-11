# Railway.app Deployment Guide

Follow these steps to deploy your **GenerativeAI Customer Support Quality Auditor** to Railway.app using Docker. This method ensures that all features, including Playwright-based email analysis, work correctly.

## 1. Prerequisites
- Your code must be pushed to a GitHub repository.
- A [Railway.app](https://railway.app/) account.

## 2. Deployment Steps
1. Log in to **Railway.app**.
2. Click **"New Project"**.
3. Select **"Deploy from GitHub repo"**.
4. Choose your repository: `Akshayaa1010/GenerativeAI-Customer-Support-Quality-Auditor`.
5. Railway will detect the `Dockerfile` automatically. Click **"Deploy Now"**.

## 3. Configuration (Variables)
You must add your API keys to the Railway environment variables:

1. In your Railway project dashboard, go to the **Variables** tab.
2. Add the following variables:
   - `GROQ_API_KEY` = `your_groq_api_key_here`
   - `PINECONE_API_KEY` = `your_pinecone_api_key_here`
3. Railway will automatically redeploy with the new settings.

## 4. Why Docker?
We use a `Dockerfile` with the official Playwright image to ensure:
- **Chromium** and all necessary system libraries are pre-installed.
- No "missing dependency" errors during email extraction.
- Consistent performance and dedicated resources.

## 5. Persistent Storage
Railway uses an ephemeral file system by default. 
- To persist `audit_results.csv`, you can add a **TCP Volume** to your service in the Railway settings.
- For production, connecting a managed database (like PostgreSQL) is recommended.
