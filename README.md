<p align="center">
  <img src="src/assets/icon.png" alt="Akili" width="140" />
</p>

<h1 align="center">Akili</h1>

<p align="center">
  AI-powered educational platform. Learn smarter with personalized AI tutoring.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Android-3DDC84?style=flat-square&logo=android&logoColor=white" alt="Android" />
  <img src="https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows11&logoColor=white" alt="Windows" />
  <img src="https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Linux" />
  <br>
  <img src="https://img.shields.io/badge/Built%20with-Flet%200.84-00B0FF?style=flat-square" alt="Built with Flet" />
  <img src="https://img.shields.io/badge/AI-Gemma%204-8E24AA?style=flat-square" alt="Gemma 4" />
</p>

---

## Features

- **AI Curriculum Generator** — Creates personalized course outlines by researching official syllabi (WAEC, NECO, JAMB).
- **Smart Lessons** — AI generates detailed lessons for each module with real curriculum data.
- **Interactive Quizzes** — Auto-generated MCQs with instant feedback and XP rewards. Always free.
- **Mock Exams** — Timed full-length assessments with grading and performance analytics.
- **AI Tutor** — Ask questions, get explanations with web-sourced answers. Markdown formatted.
- **Gamification** — XP, levels (Freshman → Genius), streaks, and achievement badges.
- **Credit System** — 150 daily credits, resets at midnight. Quizzes are always free.
- **Offline-First** — SQLite with WAL mode. Lessons cached locally after first generation.
- **Dark Mode** — Premium dark/light themes with Outfit typography.

## Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | Flet (Python → Flutter) |
| AI Backend | Self-hosted Gemma 4 31B-IT |
| Search | DuckDuckGo (client-side, no API key) |
| Database | `aiosqlite` (async SQLite, WAL mode) |
| Network | `httpx` (async, connection pooling) |
| Gateway | Cloudflare Workers (edge routing) |

## Project Structure

```
akili/
├── src/
│   ├── main.py                 # Entry point, routing
│   ├── core/
│   │   ├── constants.py        # API config, credit costs, XP rewards
│   │   ├── state.py            # Observable app state
│   │   └── theme.py            # Color palette, typography
│   ├── database/
│   │   └── manager.py          # SQLite schema + CRUD (KTV pattern)
│   ├── services/
│   │   ├── ai_service.py       # AI gateway client + search-first pipeline
│   │   ├── tools.py            # DDGS web search + content extraction
│   │   ├── credit_service.py   # Daily credit management
│   │   ├── gamification.py     # XP, levels, streaks, badges
│   │   ├── lifecycle.py        # App lifecycle (KTV pattern)
│   │   └── ad_service.py       # Mobile ad integration
│   ├── views/
│   │   ├── splash.py           # Animated splash screen
│   │   ├── onboarding.py       # Name + education level + avatar
│   │   ├── dashboard.py        # Course grid, stats, navigation
│   │   ├── course_creation.py  # AI curriculum wizard
│   │   ├── course_detail.py    # Module listing + unlock flow
│   │   ├── lesson_view.py      # AI lesson display + caching
│   │   ├── quiz_view.py        # Interactive MCQ + scoring
│   │   ├── mock_exam.py        # Timed exam + grading
│   │   ├── tutor_chat.py       # AI tutor with web search
│   │   ├── progress_view.py    # Analytics dashboard
│   │   └── settings_view.py    # Profile, theme, data management
│   └── assets/
│       └── icon.png            # App icon
├── pyproject.toml              # Dependencies + flet build config
└── README.md
```

## Credit System

| Action | Credits |
|--------|---------|
| Course Creation | 15 |
| Lesson Generation | 5 |
| Mock Exam | 10 |
| Tutor Question | 2 |
| **Practice Quiz** | **FREE** |

**150 credits/day** — resets at midnight.

## Getting Started

### Prerequisites

- Python 3.12+
- `uv` (recommended) or `pip`

### Run Locally

```bash
# Clone
git clone https://github.com/Nwokike/akili-app.git
cd akili-app

# Install dependencies
uv sync

# Run
flet run src/main.py
```

## Contributors

- **Ogechi Obinwa** — ([@Ogetec-python](https://github.com/Ogetec-python))
- **Stephen Ayankoso** — ([@Steve-ayan](https://github.com/Steve-ayan))

---

*Learn smarter, not harder* 🧠
