"""Application constants."""

# Cloudflare Worker endpoint
API_GATEWAY = "https://akili-gateway.kiri.ng"

# AI models (self-hosted gateway)
MODELS = {
    "primary": "gemma-4-31b-it",
    "fallback": "qwen3.5-122b",
}

# Credit system
DAILY_CREDITS = 150
CREDIT_COSTS = {
    "course_create": 15,
    "lesson_gen": 5,
    "quiz": 0,  # FREE — never discourage practice
    "mock_exam": 10,
    "tutor_question": 2,
    "tutor_media": 3,  # Photo/voice adds 1 extra
    "study_plan": 5,
}

# XP rewards
XP_REWARDS = {
    "lesson_complete": 10,
    "quiz_pass": 25,
    "quiz_perfect": 50,
    "mock_exam_complete": 100,
    "daily_streak": 15,
    "course_create": 20,
}

# Gamification levels
LEVELS = [
    {"name": "Freshman", "xp": 0, "icon": "🌱"},
    {"name": "Scholar", "xp": 200, "icon": "📚"},
    {"name": "Rising Star", "xp": 500, "icon": "⭐"},
    {"name": "Academic", "xp": 1000, "icon": "🎓"},
    {"name": "Prodigy", "xp": 2000, "icon": "🔬"},
    {"name": "Genius", "xp": 5000, "icon": "🧠"},
]

# Education levels
EDUCATION_LEVELS = [
    {"id": "jss1", "name": "JSS 1", "group": "Junior Secondary"},
    {"id": "jss2", "name": "JSS 2", "group": "Junior Secondary"},
    {"id": "jss3", "name": "JSS 3", "group": "Junior Secondary"},
    {"id": "ss1", "name": "SS 1", "group": "Senior Secondary"},
    {"id": "ss2", "name": "SS 2", "group": "Senior Secondary"},
    {"id": "ss3", "name": "SS 3", "group": "Senior Secondary"},
    {"id": "uni_100", "name": "100 Level", "group": "University"},
    {"id": "uni_200", "name": "200 Level", "group": "University"},
    {"id": "uni_300", "name": "300 Level", "group": "University"},
    {"id": "uni_400", "name": "400 Level", "group": "University"},
    {"id": "highschool_9", "name": "Grade 9", "group": "High School"},
    {"id": "highschool_10", "name": "Grade 10", "group": "High School"},
    {"id": "highschool_11", "name": "Grade 11", "group": "High School"},
    {"id": "highschool_12", "name": "Grade 12", "group": "High School"},
]
