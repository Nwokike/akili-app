<p align="center">
  <img src="src/assets/icon.svg" alt="Akili" width="140" />
</p>

<h1 align="center">Akili</h1>

<p align="center">
  After-School Learning App for Everyone
</p>

<p align="center">
  <a href="https://play.google.com/store/apps/details?id=ng.kiri.akili"><img src="https://img.shields.io/badge/Google_Play-Android-3DDC84?style=for-the-badge&logo=google-play&logoColor=white" alt="Google Play Store" /></a>
  <img src="https://img.shields.io/badge/Built%20with-Flet%201.0-00B0FF?style=for-the-badge&logo=flutter&logoColor=white" alt="Built with Flet" />
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
</p>

---

## Download

| Platform | Download | Notes |
|:--------:|:--------:|:------|
| 🤖 **Android** | [![Play Store](https://img.shields.io/badge/Google_Play-414141?style=flat-square&logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=ng.kiri.akili) | Recommended for most users |

### Android (APK direct download)

| Variant | Download | Notes |
|:--------:|:--------:|:-----|
| 📱 **ARM64** (most phones) | [**akili-arm64-v8a.apk**](https://github.com/Nwokike/akili-app/releases/latest/download/akili-arm64-v8a.apk) | Modern 64-bit devices |
| 📱 **ARMv7** (older phones) | [**akili-armeabi-v7a.apk**](https://github.com/Nwokike/akili-app/releases/latest/download/akili-armeabi-v7a.apk) | 32-bit ARM devices |
| 💻 **x86_64** (emulators) | [**akili-x86_64.apk**](https://github.com/Nwokike/akili-app/releases/latest/download/akili-x86_64.apk) | Chromebooks & emulators |

### Windows & Linux

Desktop builds ship with every GitHub release (`AkiliSetup.exe`, `.deb`/`.rpm`/`.tar.gz`).

---

## Core Capabilities

| Capability | Description |
|:---|:---|
| **AI Courses** | Tell Akili your class and country — it researches real curricula and builds a full course with modules, lessons, and quizzes. |
| **AI Tutor** | Ask anything in plain words, by voice, or with a photo of handwritten work. Answers cite web sources and show their reasoning. |
| **Video Lessons** | Lessons recommend YouTube videos that play right inside the app. |
| **Quizzes & Mock Exams** | Auto-generated from your lessons. Quizzes unlock the next module at 50%+; timed mock exams grade A–F. Practice is always free. |
| **Assignments** | Every lesson creates an assignment. Type or snap your answers; AI grades with per-question feedback. |
| **Gamification** | XP, levels (Freshman → Genius), daily streaks, and 7 achievement badges — shareable when you earn them. |
| **Parent Portal** | A PIN-gated overview: quiz averages, course progress, pending work, and motivation stats. |
| **Timetable** | Your weekly class schedule, with overdue-assignment reminders while the app is open. |

---

## Screenshots

> Captured on v2.0.0. Light and dark themes follow the system setting.

| Home | Tutor | Progress |
|:----:|:-----:|:--------:|
| *Courses with progress rings* | *Sourced answers with reasoning* | *XP, streaks, badges* |

---

## Credit System

Akili runs on a simple daily allowance — no account, no subscription required:

| Action | Credits |
|--------|---------|
| Course Creation | 15 |
| Lesson Generation | 5 |
| Tutor Question (text) | ~2 (per model step) |
| Tutor Question (photo/voice) | ~3 |
| Assignment Grading | 5 |
| **Practice Quiz** | **FREE** |
| **Mock Exam** | **FREE** |
| **Browsing lessons** | **FREE** |

**100 credits/day** — resets at midnight UTC. Premium raises the allowance to **500/day** and removes ads.

---

## Architecture

| Layer | Technology | Purpose |
|:---|:---|:---|
| **Frontend** | Flet 1.0.2 | Declarative cross-platform UI |
| **Text AI** | Kiri Router (`router.kiri.ng`) | Free-model inference via the kani agent loop |
| **Media AI** | Kiri Gateway (`api.kiri.ng`) | Photo transcription + voice transcription only |
| **Search** | Exa (built-in MCP) | Web research with Wikipedia/DuckDuckGo fallbacks |
| **Storage** | JSON (data tier) | Offline-first courses, progress, and settings |
| **Cache** | JSON (cache tier) | Router engine, fetched pages, tokenizers |
| **Premium** | Kiri License Worker | Signed-token entitlement, offline-verifiable |

### Visual Flow

```text
┌─────────────────────────────────────────────────────┐
│                     AKILI APP                        │
│  ┌──────┐ ┌──────────┐ ┌───────┐ ┌──────┐ ┌──────┐ │
│  │ Home │ │  Tutor   │ │Progress│ │Study │ │Settings│
│  └──┬───┘ └────┬─────┘ └──┬────┘ └──┬───┘ └──┬───┘ │
│     │          │          │         │         │     │
│  ┌──┴──────────┴──────────┴─────────┴─────────┴──┐  │
│  │         Local JSON (data tier)                 │  │
│  └──────────────────────┬─────────────────────────┘  │
└─────────────────────────┼───────────────────────────┘
              ┌───────────┴───────────┐
              ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐
│  KIRI ROUTER         │  │  KIRI GATEWAY        │
│  text + tools        │  │  photos + voice only │
└──────────────────────┘  └──────────────────────┘
```

---

## Privacy & Security

1. **Local first**: courses, lessons, progress, and settings live on your device.
2. **Ephemeral media**: photo and voice bytes are transcribed then discarded — never stored.
3. **No account**: use immediately with no sign-up or personal data.
4. **Offline-tolerant**: cached lessons read without internet; premium licenses verify offline.
5. **Encrypted transport**: all AI traffic uses TLS.

---

## Development

```bash
uv sync            # install dependencies (includes dev group)
uv run pytest -q   # run the test suite
uv run ruff check src tests   # lint
uv run flet run src/main.py   # run the app
```

Release discipline: `pyproject.toml` is the version truth (`2.0.0`, build `7`);
`src/core/constants.py`, `src/core/changelog.py`, and `version.json` follow.
`version.json` may be **held back** (lower) until the Play upload ships — never ahead.
See `docs/dependency-study.md` before adding dependencies.

---

## Legal Disclaimer

Akili is an AI-powered study companion. AI-generated lessons, quizzes, and answers
may contain mistakes — always verify against your textbooks and teachers. Akili does
not replace certified educators or official curriculum documents.
