Gitora — Code In. Clarity Out. 🚀

Gitora is an AI-powered GitHub repository analyzer that helps developers understand existing projects, explore their architecture, analyze individual files, and generate detailed technical reports.

✨ Features

- 🔗 Analyze GitHub repositories using a repository URL
- 📂 Explore repository files
- 💾 Select and save files for analysis
- 🤖 AI-powered repository analysis using Google Gemini
- 📄 File-by-file code explanation
- 🏗️ Understand project architecture and flow
- 🔌 Identify API endpoints and important requests
- 🗄️ Identify database models and database usage
- 🔐 Identify authentication-related code
- 💡 Generate 3 practical ways to rebuild or improve a project
- 💬 Ask questions about the analyzed repository
- 📑 Generate downloadable PDF reports
- ⏱️ Estimate development time
- ▶️ Provide project run instructions

🛠️ Technologies

- Python
- Flask
- Flask-SQLAlchemy
- Google Gemini API
- GitHub REST API
- SQLite
- HTML
- CSS
- JavaScript
- ReportLab

📁 Project Structure

Gitora/
│
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   │
│   ├── services/
│   │   ├── github_service.py
│   │   ├── ai_service.py
│   │   └── pdf_service.py
│   │
│   ├── templates/
│   │   ├── index.html
│   │   └── analysis.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   └── script.js
│       └── images/
│           └── hero.png
│
├── run.py
├── requirements.txt
├── .gitignore
├── README.md
└── .env

«Important: ".env" should remain local and must never be uploaded to GitHub.»

🔑 Environment Variables

Create a ".env" file in the project root:

GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash

Never publish your actual API keys.

⚙️ Installation

Clone the repository:

git clone https://github.com/YOUR_USERNAME/Gitora.git
cd Gitora

Create a virtual environment:

python -m venv venv

Activate it on Windows:

venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Create your ".env" file and add your GitHub and Gemini API credentials.

▶️ Run Gitora

Start the Flask application:

python run.py

Then open the local address shown by Flask in your browser.

🔄 How Gitora Works

GitHub Repository URL
        ↓
GitHub API
        ↓
Repository Information
        ↓
Repository Files
        ↓
Select Files
        ↓
Google Gemini AI
        ↓
Repository Analysis
        ↓
┌─────────────────────────────┐
│ Architecture                │
│ File Analysis               │
│ API Endpoints               │
│ Database                    │
│ Authentication              │
│ Project Flow                │
│ Rebuild Approaches           │
│ Development Time             │
└─────────────────────────────┘
        ↓
PDF Report / AI Chat

🤖 AI Analysis

Gitora uses Google Gemini to analyze the supplied repository source code.

The AI is instructed to base its analysis only on the repository information and source files provided to it and to avoid inventing files, APIs, frameworks, databases, or functionality.

🔒 Security

Do not commit:

.env
venv/
__pycache__/
*.pyc
*.db

API keys and private credentials should always be stored as environment variables.

🚀 Deployment

Gitora can be deployed to a cloud platform that supports Python/Flask applications.

Before deployment:

1. Add all required packages to "requirements.txt".
2. Configure "GITHUB_TOKEN" as a deployment environment variable.
3. Configure "GEMINI_API_KEY" as a deployment environment variable.
4. Configure "GEMINI_MODEL" as "gemini-3.6-flash".
5. Do not upload ".env".
6. Configure the production start command required by your hosting platform.

🎯 Purpose

Gitora is designed to make unfamiliar codebases easier to understand.

Code In. Clarity Out.

👩‍💻 Author

Built as an AI-powered developer tool for understanding, analyzing, and learning from GitHub projects.