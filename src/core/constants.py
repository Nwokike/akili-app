"""Application constants — all storage keys, credit costs, gamification, and config.

Copy deck: all user-facing strings live here (LBL_*, ERR_*, MSG_*).
Storage keys are namespaced with ``akili_`` to avoid collisions.
"""

from __future__ import annotations

# ─── App ────────────────────────────────────────────────────────────────────
APP_NAME = "Akili"
APP_VERSION = "2.0.0"
APP_BUILD_NUMBER = 7
APP_TAGLINE = "After-School Learning App for Everyone"
APP_FULL_NAME = f"{APP_NAME} — {APP_TAGLINE}"
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.akili"
SHARE_HASHTAG = "#AkiliApp #LearnSmart"
USER_AGENT = f"AkiliApp/{APP_VERSION}"

# ─── Storage keys (namespaced) ──────────────────────────────────────────────
STORAGE_THEME = "theme"
STORAGE_ONBOARDING_DONE = "onboarding_done"
STORAGE_PROFILE = "profile"
STORAGE_COURSES = "courses"
STORAGE_CREDITS = "akili_credits"
STORAGE_LAST_RESET = "akili_last_reset"
STORAGE_GAMIFICATION = "gamification"
STORAGE_AI_MODEL = "ai_model"
STORAGE_AI_MODE = "ai_mode_enabled"
STORAGE_REASONING_EFFORT = "reasoning_effort"
STORAGE_HISTORY = "search_history"
STORAGE_SEARCH_REGION = "search_region"
STORAGE_SAFESEARCH_LEVEL = "safesearch_level"
STORAGE_BIOMETRIC_LOCK = "akili_biometric_lock"

UPDATE_CONFIG_URL = "https://raw.githubusercontent.com/Nwokike/akili-app/main/version.json"


def credit_word(count: int) -> str:
    """Price copy that cannot go plural-blind: 1 credit, 3 credits.

    Every sentence quoting a credit price runs through here.
    """
    return f"{count} credit" if count == 1 else f"{count} credits"


# ─── Credit system ──────────────────────────────────────────────────────────
DAILY_FREE_CREDITS = 100
PREMIUM_DAILY_CREDITS = 500
COST_STEP = 1  # one model step = one credit
COST_TUTOR_QUESTION = 2  # per-step, not per-message
COST_TUTOR_MEDIA = 3  # a tutor message carrying image/audio (flat, finally charged)
COST_COURSE_CREATE = 15
COST_LESSON_GEN = 5
COST_ASSIGNMENT_EVAL = 5
COST_STUDY_PLAN = 5
# Quizzes and mock exams are always FREE
AD_TOPUP_CREDITS = 2
AD_TOPUP_COOLDOWN_SEC = 30.0

# ─── Gamification ───────────────────────────────────────────────────────────
LEVELS = [
    {"name": "Freshman", "xp": 0, "icon": "🌱"},
    {"name": "Scholar", "xp": 200, "icon": "📚"},
    {"name": "Rising Star", "xp": 500, "icon": "⭐"},
    {"name": "Academic", "xp": 1000, "icon": "🎓"},
    {"name": "Prodigy", "xp": 2000, "icon": "🔬"},
    {"name": "Genius", "xp": 5000, "icon": "🧠"},
]

XP_REWARDS = {
    "lesson_complete": 10,
    "quiz_pass": 25,
    "quiz_perfect": 50,
    "mock_exam_complete": 100,
    "daily_streak": 15,
    "course_create": 20,
    "tutor_question": 5,
    "assignment_on_time": 30,
    "assignment_late": 10,
    "assignment_perfect": 50,
}

BADGE_DEFINITIONS = {
    "first_course": {"name": "First Course", "icon": "🎯", "desc": "Created your first course"},
    "perfect_quiz": {"name": "Perfect Score", "icon": "💯", "desc": "Got 100% on a quiz"},
    "week_streak": {"name": "Week Warrior", "icon": "🔥", "desc": "7-day study streak"},
    "ten_lessons": {"name": "Bookworm", "icon": "📖", "desc": "Completed 10 lessons"},
    "first_mock": {"name": "Exam Ready", "icon": "📝", "desc": "Completed first mock exam"},
    "honor_roll": {"name": "Honor Roll", "icon": "🏆", "desc": "Average score above 80%"},
    "diligent_scholar": {"name": "Diligent Scholar", "icon": "✍️", "desc": "Completed 10 assignments on time"},
}

# ─── Education systems ──────────────────────────────────────────────────────
SYSTEM_TEMPLATES = {
    "WAEC": {
        "name": "West African (WAEC)",
        "levels": ["JSS 1", "JSS 2", "JSS 3", "SSS 1", "SSS 2", "SSS 3"],
    },
    "K12": {
        "name": "International (Grade 1-12)",
        "levels": [f"Grade {i}" for i in range(1, 13)],
    },
    "UK": {
        "name": "UK / Commonwealth (Year 1-13)",
        "levels": [f"Year {i}" for i in range(1, 14)],
    },
    "CBC": {
        "name": "Competency-Based (Kenya/Others)",
        "levels": [f"Grade {i}" for i in range(1, 13)],
    },
    "UNI": {
        "name": "University / Higher Ed",
        "levels": ["Year 1", "Year 2", "Year 3", "Year 4", "Masters", "PhD"],
    },
}

# ─── Countries (ISO 3166-1 alpha-2 simplified) ──────────────────────────────
COUNTRIES = sorted(
    [
        "Afghanistan",
        "Albania",
        "Algeria",
        "Andorra",
        "Angola",
        "Antigua and Barbuda",
        "Argentina",
        "Armenia",
        "Australia",
        "Austria",
        "Azerbaijan",
        "Bahamas",
        "Bahrain",
        "Bangladesh",
        "Barbados",
        "Belarus",
        "Belgium",
        "Belize",
        "Benin",
        "Bhutan",
        "Bolivia",
        "Bosnia and Herzegovina",
        "Botswana",
        "Brazil",
        "Brunei",
        "Bulgaria",
        "Burkina Faso",
        "Burundi",
        "Cabo Verde",
        "Cambodia",
        "Cameroon",
        "Canada",
        "Central African Republic",
        "Chad",
        "Chile",
        "China",
        "Colombia",
        "Comoros",
        "Congo",
        "Costa Rica",
        "Croatia",
        "Cuba",
        "Cyprus",
        "Czechia",
        "Denmark",
        "Djibouti",
        "Dominica",
        "Dominican Republic",
        "Ecuador",
        "Egypt",
        "El Salvador",
        "Equatorial Guinea",
        "Eritrea",
        "Estonia",
        "Eswatini",
        "Ethiopia",
        "Fiji",
        "Finland",
        "France",
        "Gabon",
        "Gambia",
        "Georgia",
        "Germany",
        "Ghana",
        "Greece",
        "Grenada",
        "Guatemala",
        "Guinea",
        "Guinea-Bissau",
        "Guyana",
        "Haiti",
        "Holy See",
        "Honduras",
        "Hungary",
        "Iceland",
        "India",
        "Indonesia",
        "Iran",
        "Iraq",
        "Ireland",
        "Israel",
        "Italy",
        "Jamaica",
        "Japan",
        "Jordan",
        "Kazakhstan",
        "Kenya",
        "Kiribati",
        "Kuwait",
        "Kyrgyzstan",
        "Laos",
        "Latvia",
        "Lebanon",
        "Lesotho",
        "Liberia",
        "Libya",
        "Liechtenstein",
        "Lithuania",
        "Luxembourg",
        "Madagascar",
        "Malawi",
        "Malaysia",
        "Maldives",
        "Mali",
        "Malta",
        "Marshall Islands",
        "Mauritania",
        "Mauritius",
        "Mexico",
        "Micronesia",
        "Moldova",
        "Monaco",
        "Mongolia",
        "Montenegro",
        "Morocco",
        "Mozambique",
        "Myanmar",
        "Namibia",
        "Nauru",
        "Nepal",
        "Netherlands",
        "New Zealand",
        "Nicaragua",
        "Niger",
        "Nigeria",
        "North Korea",
        "North Macedonia",
        "Norway",
        "Oman",
        "Pakistan",
        "Palau",
        "Palestine State",
        "Panama",
        "Papua New Guinea",
        "Paraguay",
        "Peru",
        "Philippines",
        "Poland",
        "Portugal",
        "Qatar",
        "Romania",
        "Russia",
        "Rwanda",
        "Saint Kitts and Nevis",
        "Saint Lucia",
        "Saint Vincent and the Grenadines",
        "Samoa",
        "San Marino",
        "Sao Tome and Principe",
        "Saudi Arabia",
        "Senegal",
        "Serbia",
        "Seychelles",
        "Sierra Leone",
        "Singapore",
        "Slovakia",
        "Slovenia",
        "Solomon Islands",
        "Somalia",
        "South Africa",
        "South Korea",
        "South Sudan",
        "Spain",
        "Sri Lanka",
        "Sudan",
        "Suriname",
        "Sweden",
        "Switzerland",
        "Syria",
        "Tajikistan",
        "Tanzania",
        "Thailand",
        "Timor-Leste",
        "Togo",
        "Tonga",
        "Trinidad and Tobago",
        "Tunisia",
        "Turkey",
        "Turkmenistan",
        "Tuvalu",
        "Uganda",
        "Ukraine",
        "United Arab Emirates",
        "United Kingdom",
        "United States of America",
        "Uruguay",
        "Uzbekistan",
        "Vanuatu",
        "Venezuela",
        "Vietnam",
        "Yemen",
        "Zambia",
        "Zimbabwe",
    ]
) + ["Other"]

# ─── Kiri router (AI backend) ───────────────────────────────────────────────
ENGINE_URL = "https://router.kiri.ng/run.py"
ROUTER_HOST = "127.0.0.1"
ROUTER_BASE_PORT = 8082
ROUTER_SPAN = 10  # scan 8082..8092 for a running Kiri router
ROUTER_STICKY_COOLDOWN = 60.0  # cool-off after a router failure
PROBE_MISS_TTL = 30.0  # remember a full port-scan miss this long

# ─── Agent ──────────────────────────────────────────────────────────────────
ANSWER_MAX_TOKENS = 2048
TEMPERATURE = 0.4
DEFAULT_CONTEXT = 131072  # generous; a 30-message transcript never evicts
AGENT_MAX_ITERS = 6  # model calls per turn (worst case 6 * COST_STEP)
AGENT_MAX_TOOLS = 10  # tool calls per turn
AGENT_TIMEOUT_S = 240  # wall-clock per turn
TOOL_OUTPUT_CAP = 8000  # chars of tool output re-sent per loop
AGENT_HISTORY_MESSAGES = 30
SEARCH_TIMEOUT = 25.0
FETCH_TIMEOUT = 25.0
SEARCH_ENDPOINT = "https://mcp.exa.ai/mcp"
API_SAFE_SEARCH = "wt-wt"  # DuckDuckGo fallback region
STORAGE_PARENT_PIN = "parent_pin"
DEFAULT_PARENT_PIN = "1234"

# ─── MCP ────────────────────────────────────────────────────────────────────
MCP_CONNECT_TIMEOUT = 20.0
MCP_DIAGNOSE_TIMEOUT = 5.0
MCP_DESC_CAP = 4000
STORAGE_MCP_SERVERS = "mcp_servers"

# ─── Ad units ───────────────────────────────────────────────────────────────
# LIVE Akili units (from v1 ad_service.py). Never replace with another
# app's units — the publisher prefix matches across Kiri apps, but the
# suffix is per-app inventory. Sherlock's units were copied here once
# by mistake; do not repeat that.
AD_BANNER_UNIT_ID = "ca-app-pub-5679949845754640/1712130979"
AD_INTERSTITIAL_UNIT_ID = "ca-app-pub-5679949845754640/5238266847"

# ─── Kiri License ───────────────────────────────────────────────────────────
KIRI_LICENSE_BASE_URL = "https://license.kiri.ng"
KIRI_LICENSE_PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE-YfZ-yKdG3wYF1IR0XcpJH4RclABnddMmAGXFI2J8sbC4gWY2POKc8hVrn0_uHxDZ9ufzwzg4buUimW-IEw4Uw"
KIRI_LICENSE_APP_ID = "ng.kiri.akili"
KIRI_LICENSE_TIMEOUT = 15.0

# ─── Contact ────────────────────────────────────────────────────────────────
CONTACT_EMAIL = "hello@kiri.ng"
GITHUB_REPO_URL = "https://github.com/Nwokike/akili-app"
KIRI_APPS_PLAY_URL = "https://play.google.com/store/apps/dev?id=5797833969564243342"
KIRI_APPS_URL = "https://kiri.ng/projects"

# ─── User-facing strings (copy deck) ────────────────────────────────────────
LBL_APP_NAME = "Akili"
LBL_TAGLINE = "After-School Learning App for Everyone"
LBL_LOADING = "Loading..."
LBL_OFFLINE = "You're offline."
LBL_ONLINE = "You're back online."
LBL_NO_INTERNET = "No internet connection."
LBL_RETRY = "Try again"
LBL_CANCEL = "Cancel"
LBL_OK = "OK"
LBL_CLOSE = "Close"
LBL_SAVE = "Save"
LBL_DELETE = "Delete"
LBL_EDIT = "Edit"
LBL_SEARCH = "Search"
LBL_SETTINGS = "Settings"
LBL_HOME = "Home"
LBL_PROGRESS = "Progress"
LBL_DASHBOARD = "Dashboard"
LBL_COURSES = "Courses"
LBL_LESSONS = "Lessons"
LBL_QUIZZES = "Quizzes"
LBL_EXAMS = "Exams"
LBL_TUTOR = "AI Tutor"
LBL_ASSIGNMENTS = "Assignments"
LBL_TIMETABLE = "Timetable"
LBL_PARENT_PORTAL = "Parent Portal"
LBL_HISTORY = "History"
LBL_VIEW_HISTORY = "View Detailed History"
LBL_ADD_TIMETABLE_ENTRY = "Add Class"
LBL_EDIT_TIMETABLE_ENTRY = "Edit Class"
LBL_TIMETABLE_EMPTY = "No schedule yet"
LBL_TIMETABLE_EMPTY_DESC = "Add your first class below"
LBL_TIMETABLE_TODAY = "Today"
LBL_PARENT_LOCK_TITLE = "Parental Gate"
LBL_PARENT_LOCK_DESC = "Enter the 4-digit PIN to view the student overview."
LBL_PARENT_UNLOCK = "Unlock"
LBL_PARENT_WRONG_PIN = "Incorrect PIN"
LBL_PARENT_CHANGE_PIN = "Change PIN"
LBL_PARENT_NEW_PIN = "New PIN"
LBL_PARENT_CONFIRM_PIN = "Confirm PIN"
LBL_PARENT_PIN_CHANGED = "PIN changed."
LBL_PARENT_PIN_MISMATCH = "PINs do not match."
LBL_PARENT_PIN_SHORT = "PIN must be 4 digits."
LBL_PARENT_STUDENT_OVERVIEW = "Student Overview"
LBL_PARENT_TOTAL_QUIZZES = "Total quizzes taken"
LBL_PARENT_AVG_SCORE = "Average score"
LBL_PARENT_LAST_ACTIVE = "Last active"
LBL_SHARE_STREAK = "Share Streak"
LBL_SHARE_LEVEL = "Share Level"
LBL_ACHIEVEMENTS = "Achievements"
LBL_QUIZ_PERFORMANCE = "Quiz Performance"
LBL_AVG_SCORE_LABEL = "Avg Score"
LBL_QUIZZES_LABEL = "Quizzes"
LBL_SHARE_ACHIEVEMENT = "Share Achievement 🎉"
LBL_PREMIUM = "Premium"
LBL_CREDITS = "Credits"
LBL_THEME = "Theme"
LBL_LIGHT = "Light"
LBL_DARK = "Dark"
LBL_SYSTEM = "System"
LBL_ABOUT = "About"
LBL_VERSION = "Version"
LBL_UPDATE_AVAILABLE = "Update Available"
LBL_UP_TO_DATE = "You're up to date!"
LBL_CHECK_FOR_UPDATES = "Check for Updates"
LBL_WHATS_NEW = "What's New"
LBL_PRIVACY_OPTIONS = "Privacy Options"
LBL_CONTACT = "Contact"
LBL_RATE = "Rate"
LBL_MORE_APPS = "More apps"
LBL_RESTORE = "Restore"
LBL_RECOVERY_ID = "Recovery ID"
LBL_COPY = "Copy"
LBL_COPIED = "Copied!"
LBL_PREMIUM_ACTIVE = "Premium active"
LBL_PREMIUM_UNLOCKED = "Premium unlocked!"
LBL_GET_CREDITS = "Get credits"
LBL_WATCH_AD = "Watch ad for +2 credits"
LBL_DAILY_RESET = "Resets at 00:00 UTC"
LBL_CREDITS_LEFT = "credits left today"
LBL_COST_PER_STEP = "Each AI model step costs"
LBL_FREE = "Free"
LBL_QUIZ_FREE = "Practice quizzes are always free"
LBL_EXAM_FREE = "Mock exams are always free"
LBL_ONBOARDING_TITLE = "Personalize Akili"
LBL_ONBOARDING_SUBTITLE = "Tell us about your learning journey."
LBL_YOUR_NAME = "Full Name"
LBL_YOUR_LEVEL = "Your Class / Level"
LBL_YOUR_COUNTRY = "Your Country"
LBL_GET_STARTED = "Get Started"
LBL_LEVEL_EXAMPLES = "Examples: JSS 1, SSS 2, Primary 5, Form 3, Grade 7, Year 2, University Year 1..."
LBL_ERROR_NAME_LEVEL = "Please enter your name and class/level"
LBL_EMPTY_COURSES = "No courses yet"
LBL_EMPTY_COURSES_DESC = "Create your first course to get started"
LBL_CREATE_COURSE = "Create Course"
LBL_EMPTY_PROGRESS = "No progress yet"
LBL_EMPTY_PROGRESS_DESC = "Start learning to see your progress"
LBL_CREATE_COURSE = "Create Course"
LBL_NEW_COURSE = "New Course"
LBL_COURSE_TITLE = "Course Title"
LBL_SUBJECT = "Subject"
LBL_LEVEL = "Level"
LBL_GENERATE = "Generate"
LBL_GENERATING = "Generating..."
LBL_LESSON_TITLE = "Lesson"
LBL_LESSON_CONTENT = "Lesson Content"
LBL_MARK_COMPLETE = "Mark Complete"
LBL_NEXT_LESSON = "Next Lesson"
LBL_PREV_LESSON = "Previous Lesson"
LBL_START_QUIZ = "Start Quiz"
LBL_START_EXAM = "Start Exam"
LBL_VIEW_RESULTS = "View Results"
LBL_SCORE = "Score"
LBL_CORRECT = "Correct"
LBL_INCORRECT = "Incorrect"
LBL_TIME_SPENT = "Time Spent"
LBL_XP_EARNED = "XP Earned"
LBL_STREAK = "Streak"
LBL_BADGES = "Badges"
LBL_LEVEL_UP = "Level Up!"
LBL_SHARE = "Share"
LBL_TUTOR_PLACEHOLDER = "Ask me anything..."
LBL_TUTOR_SEND = "Send"
LBL_TUTOR_STOP = "Stop"
LBL_TUTOR_THINKING = "Thinking..."
LBL_TUTOR_THIS = "Thought for {seconds}s"
LBL_TUTOR_STEPS = "{steps} steps · {cost} credits · {model} · {tokens} tok"
LBL_TUTOR_LOW_BALANCE = "Low credit balance. This message finishes regardless."
LBL_TUTOR_OUT_OF_CREDITS = "Out of assistant credits"
LBL_TUTOR_EMPTY = "The AI didn't produce an answer. Not charged."
LBL_TUTOR_MIDSTREAM = "The AI stopped mid-answer. You were charged for what you saw."
LBL_TUTOR_UNAVAILABLE = "The AI is unavailable right now. Try again shortly."
LBL_STEP_RUNNING = "Running..."
LBL_STEP_DONE = "Done"
LBL_STEP_ERROR = "Error"
LBL_APPROVE = "Approve"
LBL_DENY = "Deny"
LBL_AUTO_DENY = "Auto-denies in {seconds}s"
LBL_WRITE_TOOL_DECLINED = "User declined this action"
LBL_ASSIGNMENT_TITLE = "Assignment"
LBL_ASSIGNMENT_SUBMIT = "Submit"
LBL_ASSIGNMENT_GRADE = "Grade"
LBL_ASSIGNMENT_FEEDBACK = "Feedback"
LBL_ASSIGNMENT_SCORE = "Score"
LBL_PARENT_OVERVIEW = "Overview"
LBL_PARENT_CHILDREN = "Children"
LBL_PARENT_REPORTS = "Reports"
LBL_PARENT_SETTINGS = "Settings"
LBL_TIMETABLE_ADD = "Add"
LBL_TIMETABLE_DAY = "Day"
LBL_TIMETABLE_TIME = "Time"
LBL_TIMETABLE_SUBJECT = "Subject"
LBL_TIMETABLE_MONDAY = "Monday"
LBL_TIMETABLE_TUESDAY = "Tuesday"
LBL_TIMETABLE_WEDNESDAY = "Wednesday"
LBL_TIMETABLE_THURSDAY = "Thursday"
LBL_TIMETABLE_FRIDAY = "Friday"
LBL_TIMETABLE_SATURDAY = "Saturday"
LBL_TIMETABLE_SUNDAY = "Sunday"
LBL_DATA_MANAGEMENT = "Data Management"
LBL_CLEAR_CACHE = "Clear Cache"
LBL_CLEAR_HISTORY = "Clear History"
LBL_RESET_APP = "Reset App"
LBL_CLEARING = "Clearing..."
LBL_RESETTING = "Resetting..."
LBL_ACTIVITY_TERMINAL = "Activity Terminal"
LBL_LOGS_COUNT = "{count} entries in memory"
LBL_COPYRIGHT = "© 2026 Kiri Research Labs"
LBL_MADE_WITH = "Made with Flet"
LBL_PRIVACY_POLICY = "Privacy Policy"
LBL_TERMS_OF_SERVICE = "Terms of Service"
LBL_USAGE_AGREEMENT = "Usage Agreement"
LBL_SELECT_ALL = "Select All"
LBL_DESELECT_ALL = "Deselect All"
LBL_POPULAR = "Popular"
LBL_FILTER = "Filter"
LBL_SORT = "Sort"
LBL_REFRESH = "Refresh"
LBL_LOADING_MODELS = "Loading models..."
LBL_START_ROUTER = "Start router"
LBL_ROUTER_OFFLINE = "Offline"
LBL_ROUTER_STARTING = "Starting router..."
LBL_MODEL_AUTO = "Auto (recommended)"
LBL_MODEL_ROTATES = "Rotates across available models"
LBL_MCP_SERVERS = "MCP Servers"
LBL_MCP_ADD = "Add Server"
LBL_MCP_CONNECT = "Connect"
LBL_MCP_DISCONNECT = "Disconnect"
LBL_MCP_STATUS = "Status"
LBL_MCP_TOOLS = "Tools"
LBL_MCP_NAME = "Name"
LBL_MCP_URL = "URL"
LBL_MCP_TRANSPORT = "Transport"
LBL_MCP_API_KEY = "API Key"
LBL_MCP_ENABLED = "Enabled"
LBL_MCP_DISABLED = "Disabled"
LBL_MCP_CONNECTED = "Connected"
LBL_MCP_DISCONNECTED = "Disconnected"
LBL_MCP_ERROR = "Error"
LBL_MCP_TIMEOUT = "Timed out"
LBL_MCP_UNREACHABLE = "Server unreachable. Check the URL or command."
LBL_MCP_AUTH_FAILED = "Authentication failed. Check the headers or key."
LBL_MCP_PROTOCOL_ERROR = "Server speaks an incompatible MCP protocol version."
LBL_MCP_CONFIG_ERROR = "Configuration error"
LBL_MCP_STDIO_MOBILE = "stdio transport is not supported on mobile devices. Use streamable_http or sse."
LBL_MCP_COMMAND_NOT_FOUND = "`{command}` was not found on this device, so the {name} MCP server cannot start."
LBL_MCP_INSTALL_UVX = "Install uv (https://docs.astral.sh/uv/) so `uvx` is on your PATH, or add a streamable_http server instead."
LBL_MCP_INSTALL_NPX = "Install Node.js so `npx` is on your PATH, or add a streamable_http server instead."
LBL_MCP_INSTALL_NODE = "Install Node.js so `node` is on your PATH, or add a streamable_http server instead."
LBL_MCP_INSTALL_DENO = "Install Deno, or add a streamable_http server instead."
LBL_MCP_INSTALL_BUNX = "Install Bun, or add a streamable_http server instead."
LBL_MCP_INSTALL_COMMAND = "Make sure `{command}` is installed and on your PATH."
LBL_MCP_SOME_UNAVAILABLE = "Some MCP servers unavailable: {details}"
LBL_MCP_CONNECTION_FAILED = "MCP connection failed: {error}"
LBL_MCP_ERROR_STATUS = "MCP error: {error}"
LBL_MCP_ABSORBED_CANCEL = "MCP owner absorbed a foreign cancel; continuing"
LBL_MCP_OWNER_WAIT_FAILED = "MCP owner wait failed: {error}"
LBL_MCP_DISCONNECT = "MCP disconnect: {error}"
LBL_MCP_CLEANUP_FAILED = "MCP owner cleanup failed: {error}"
LBL_MCP_APPLY_FAILED = "MCP apply failed: {error}"
LBL_MCP_CONNECTED_TOOLS = "MCP connected: {tools} tools from {connected}/{total} servers ({blocked} blocked)"
LBL_MCP_STATUS_CALLBACK_FAILED = "MCP status callback failed: {error}"
LBL_MCP_TOOL_FAILED = "Tool {name} failed: {error}"
LBL_MCP_TOOL_TIMED_OUT = "MCP {name} timed out after {seconds}s; other servers still load"
LBL_MCP_TOOL_CONNECT_CANCELLED = "MCP {name} connect cancelled after {seconds}s; other servers still load"
LBL_MCP_TOOL_CONNECT_FAILED = "MCP {name} failed during connect: {error}"
LBL_MCP_TOOL_SKIPPED = "MCP {name} skipped: {error}"
LBL_MCP_STDIO_DIAGNOSE = "When a stdio child dies during connect, ask it why."
LBL_MCP_STDIO_DIAGNOSE_DETAIL = "{error}. Server output: {output}"
LBL_MCP_CONNECTION_CLOSED = "Connection closed"
LBL_MCP_SERVER_UNREACHABLE = "Server unreachable. Check the URL or command."
LBL_MCP_AUTH_FAILED_DETAIL = "Authentication failed. Check the headers or key."
LBL_MCP_PROTOCOL_VERSION_ERROR = "Server speaks an incompatible MCP protocol version."
LBL_MCP_TOOL_ERROR = "{error}"
LBL_MCP_UNKNOWN_SCHEMA_TYPE = "Unknown schema type {kind}"
LBL_MCP_PROPERTIES_REQUIRES_OBJECT = "properties requires type 'object'"
LBL_MCP_SCHEMA_NOT_OBJECT = "schema is not a JSON object"
LBL_MCP_TOOL_ROW_WITHOUT_ID = "a row without its id never closes"
LBL_MCP_TOOL_DESC_TRUNCATED = "{description}...(truncated)"
LBL_MCP_PARTIAL_STATUS = 'Honest partial status rather than a silent "all good".'
LBL_MCP_DESC_TOO_LONG = "Remote servers are untrusted: cap what one can push into EVERY future request (a huge tool description is both a token bomb and a prompt-injection surface)."
LBL_MCP_TOOL_LABEL = "User-legible tool label: verb first, no quotes, no trailing ellipsis."
LBL_MCP_APPROVAL_DETAIL = "The arguments a user needs before approving a write, as plain text."
LBL_MCP_TOOL_OUTCOME = "A short, human-readable consequence of a write tool."
LBL_MCP_NO_RESULTS = "no results"
LBL_MCP_SAVED_TO = "saved to {filename}"
LBL_MCP_PAGES_SAVED = "{count} page{s} saved"
LBL_MCP_PAGES_SAVED_FAILED = "{count} page{s} saved, {failed} failed"
LBL_MCP_NOTHING_TO_CANCEL = "nothing to cancel"
LBL_MCP_REMOVED = "{count} removed"
LBL_MCP_EVERY_MINUTES = "every {minutes} minutes"
LBL_MCP_SCHEDULED = "Runs while the app is open"
LBL_MCP_CANCELLED = "cancelled"
LBL_MCP_UNKNOWN_TOOL = "Running {name}"
LBL_MCP_SEARCHING_WEB = "Searching the web: {query}"
LBL_MCP_SEARCHING_IMAGES = "Searching images: {query}"
LBL_MCP_SEARCHING_VIDEOS = "Searching videos: {query}"
LBL_MCP_SEARCHING_NEWS = "Searching news: {query}"
LBL_MCP_SEARCHING_BOOKS = "Searching books: {query}"
LBL_MCP_FETCHING = "Fetching {host}"
LBL_MCP_SAVING = "Saving {host} as {format}"
LBL_MCP_DOWNLOADING = "Downloading media from {host}"
LBL_MCP_CRAWLING = "Crawling {host}"
LBL_MCP_SCHEDULING = "Scheduling a crawl of {host}"
LBL_MCP_CANCELLING = "Cancelling scheduled crawl"
LBL_MCP_TURN_STOPPED = "User pressed Stop."
LBL_MCP_TURN_CANCELLED = "Hard cancel (the Stop button)."
LBL_MCP_TURN_SETTLED = "settle by what was delivered, then let the cancellation through."
LBL_MCP_TURN_BILLED = "a step that put tokens on the screen is billable"
LBL_MCP_TURN_REFUND = "Refunding that would give away delivered work"
LBL_MCP_TURN_EMPTY = "The model was called and said nothing. Charging a user for an empty bubble is the kind of thing that makes a paywall feel dishonest"
LBL_MCP_TURN_CHARGED = "partial work delivered - charge it"
LBL_MCP_TURN_FAILED = "chat turn failed"
LBL_MCP_TURN_UNAVAILABLE = "chat turn unavailable: {error}"
LBL_MCP_TURN_CANCELLED_AFTER = "chat turn cancelled after {steps} step(s)"
LBL_MCP_TURN_NO_ANSWER = "chat turn produced no answer after {steps} step(s); not charged"
LBL_MCP_SETTLE_IDEMPOTENT = "settlement for {tx_id} already applied"
LBL_MCP_SETTLE_ROLLBACK_DEFERRED = "rollback deferred, turn active (tx: {tx_id})"
LBL_MCP_SETTLE_AUTO_ROLLBACK = "Auto-rolled back {amount} reserved credits (tx: {tx_id})."
LBL_MCP_SETTLE_CHARGED = "Charged {amount} credits. Remaining: {balance}"
LBL_MCP_SETTLE_ADDED = "Added {amount} credits. New balance: {balance}"
LBL_MCP_SETTLE_SPENT = "Spent {amount} credits. Remaining: {balance}"
LBL_MCP_SETTLE_DAILY_RESET = "Daily credit reset: balance preserved/topped up at {balance}."
LBL_MCP_SETTLE_BALANCE_PRESERVED = "balance preserved/topped up at {balance}"
LBL_MCP_CREDIT_WORD = "{count} credit"
LBL_MCP_CREDITS_WORD = "{count} credits"
LBL_MCP_CREDIT_PILL_GREEN = ">20"
LBL_MCP_CREDIT_PILL_AMBER = ">=5"
LBL_MCP_CREDIT_PILL_RED = "<5"
LBL_MCP_WALLET_BALANCE = "of {cap} daily · resets 00:00 UTC"
LBL_MCP_WALLET_COST_TABLE = "Cost table generated from COST_STEP"
LBL_MCP_WALLET_AD_TOPUP = "+{credits} credits (watch ad)"
LBL_MCP_WALLET_AD_COOLDOWN = "Available in {seconds}s"
LBL_MCP_WALLET_AD_PREMIUM_DISABLED = "Disabled (premium)"
LBL_MCP_WALLET_GET_PREMIUM = "Get {credits} credits a day"
LBL_MCP_WALLET_PREMIUM_ACTIVE = "Premium active. Ads off, {credits} assistant credits/day."
LBL_MCP_WALLET_PREMIUM_NO_ADS = "Premium active. {credits} assistant credits/day."
LBL_MCP_WALLET_PREMIUM_GRANTED = "Premium active. Ads off, {credits} assistant credits/day."
LBL_MCP_WALLET_PREMIUM_GRANTED_NO_ADS = "Premium active. {credits} assistant credits/day."
LBL_MCP_WALLET_PREMIUM_BENEFITS = "Top up to the premium credit cap on the transition into Premium."
LBL_MCP_WALLET_PREMIUM_BENEFITS_FAILED = "premium init failed"
LBL_MCP_WALLET_PREMIUM_RECONCILE = "Resolve Premium at startup from both channels."
LBL_MCP_WALLET_PREMIUM_RECONCILE_FAILED = "premium reconcile failed"
LBL_MCP_WALLET_PREMIUM_RECONCILE_HOURLY = "Hourly check keeps renewals and revokes current while the app runs"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME = "Re-check the licence on resume, as the client contract asks."
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_DEBOUNCED = "Debounced (KTV Player): RESUME/SHOW arrives in bursts, and each burst would otherwise burn the Worker's shared 20 req/60s budget."
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_SKIPPED = "licence refresh on resume skipped: {error}"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_FAILED = "premium reconcile on resume failed: {error}"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_SUCCESS = "premium reconcile on resume succeeded"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_CHANGED = "premium status changed on resume"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_UNCHANGED = "premium status unchanged on resume"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_ERROR = "premium reconcile on resume failed: {error}"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_OFFLINE = "premium reconcile on resume skipped (offline)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_ONLINE = "premium reconcile on resume (online)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY = "premium reconcile on resume (retry)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FAILED = "premium reconcile on resume (retry failed)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_SUCCESS = "premium reconcile on resume (retry succeeded)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_UNCHANGED = "premium reconcile on resume (retry unchanged)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_ERROR = "premium reconcile on resume (retry failed: {error})"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_OFFLINE = "premium reconcile on resume (retry skipped, offline)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_ONLINE = "premium reconcile on resume (retry, online)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_WAITING = "premium reconcile on resume (retry, waiting)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_CANCELLED = "premium reconcile on resume (retry cancelled)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_TIMEOUT = "premium reconcile on resume (retry timed out)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_EXHAUSTED = "premium reconcile on resume (retry exhausted)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_GIVE_UP = "premium reconcile on resume (giving up)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL = "premium reconcile on resume (final attempt)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_FAILED = "premium reconcile on resume (final attempt failed)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_SUCCESS = "premium reconcile on resume (final attempt succeeded)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_UNCHANGED = "premium reconcile on resume (final attempt unchanged)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_ERROR = "premium reconcile on resume (final attempt failed: {error})"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_OFFLINE = "premium reconcile on resume (final attempt skipped, offline)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_ONLINE = "premium reconcile on resume (final attempt, online)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_WAITING = "premium reconcile on resume (final attempt, waiting)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_CANCELLED = "premium reconcile on resume (final attempt cancelled)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_TIMEOUT = "premium reconcile on resume (final attempt timed out)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_EXHAUSTED = "premium reconcile on resume (final attempt exhausted)"
LBL_MCP_WALLET_PREMIUM_RECONCILE_RESUME_RETRY_FINAL_GIVE_UP = "premium reconcile on resume (final attempt, giving up)"
