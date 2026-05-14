# 🤖 CodeSense - AI-Powered Automated Code Review Platform

CodeSense is a robust, multi-agent automated code review system built with **FastAPI, Next.js, LangGraph, and Groq**. It connects directly to your GitHub repositories via webhooks, acting as an autonomous, extremely intelligent senior engineer that reviews Pull Requests instantly.

## 🌟 Key Features

- **Parallel Multi-Agent Review:** Utilizes specialized LangChain/Groq agents (Security, Performance, Logic, and Style) working in parallel to deeply analyze PR diffs.
- **Synthesis Engine:** A master synthesis agent deduplicates findings, calculates severity (Critical, Warning, Info), and posts a consolidated review directly to the GitHub Pull Request.
- **Long-Term Memory:** Integrates **Qdrant Vector Database** to remember past code mistakes, enabling the AI to flag "Recurring Pattern" issues across multiple PRs.
- **Analytics Dashboard:** A beautiful **Next.js** frontend dashboard using Recharts to visualize repository health, agent activity, and review history.
- **Automated Email Summaries:** Sends immediate email notifications to developers summarizing the AI review, including severity breakdowns and actionable fixes.
- **Auto-Documentation Companion:** Listens for merged PRs and automatically updates the repository's `README.md` via AI to reflect the new changes, pushing the commit directly to the branch.

## 🏗️ Architecture

```
CodeSense/
├── backend/          # FastAPI server, LangGraph agents, Qdrant memory, GitHub Webhooks
└── frontend/         # Next.js 14 App Router, Tailwind CSS, Recharts dashboard
```

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Groq API Key](https://console.groq.com/)
- GitHub Personal Access Token (with `repo` scope)
- (Optional) SMTP Credentials for Emails

### Environment Variables
1. Navigate to `backend/` and copy `.env.example` to `.env`.
2. Fill in your `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `GROQ_API_KEY`, and optional `SMTP` credentials.

### Running Locally

You can use the provided `start.bat` script in the root directory to boot both the backend and frontend simultaneously, or run them manually:

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Connecting to GitHub
To test locally, use `ngrok` to expose your backend to the internet:
```bash
ngrok http 8000
```
Then go to your GitHub Repository -> Settings -> Webhooks -> Add Webhook:
- **Payload URL:** `https://<your-ngrok-url>.ngrok-free.app/api/webhook`
- **Content type:** `application/json`
- **Secret:** The same secret you put in your backend `.env`
- **Events:** Select "Pull requests"

## 🧪 Running Tests
The backend uses `pytest` for rigorous unit testing of agents, memory retrieval, and API integration.
```bash
cd backend
pytest -v
```

---
*Built as a state-of-the-art agentic workflow demonstration.*
