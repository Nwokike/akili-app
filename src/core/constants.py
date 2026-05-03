
API_GATEWAY = "https://akili-gateway.kiri.ng"


class AITaskType:
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"

DAILY_CREDITS = 150
CREDIT_COSTS = {
    "course_create": 15,
    "lesson_gen": 5,
    "quiz": 0,
    "mock_exam": 10,
    "tutor_question": 2,
    "tutor_media": 3,
    "study_plan": 5,
}

XP_REWARDS = {
    "lesson_complete": 10,
    "quiz_pass": 25,
    "quiz_perfect": 50,
    "mock_exam_complete": 100,
    "daily_streak": 15,
    "course_create": 20,
    "tutor_question": 5,
}

LEVELS = [
    {"name": "Freshman", "xp": 0, "icon": "🌱"},
    {"name": "Scholar", "xp": 200, "icon": "📚"},
    {"name": "Rising Star", "xp": 500, "icon": "⭐"},
    {"name": "Academic", "xp": 1000, "icon": "🎓"},
    {"name": "Prodigy", "xp": 2000, "icon": "🔬"},
    {"name": "Genius", "xp": 5000, "icon": "🧠"},
]

EDUCATION_LEVELS = [
    {"id": "middle_school", "name": "Middle School", "group": "Secondary"},
    {"id": "grade_9", "name": "Grade 9", "group": "Secondary"},
    {"id": "grade_10", "name": "Grade 10", "group": "Secondary"},
    {"id": "grade_11", "name": "Grade 11", "group": "Secondary"},
    {"id": "grade_12", "name": "Grade 12", "group": "Secondary"},
    {"id": "freshman", "name": "University — Year 1", "group": "University"},
    {"id": "sophomore", "name": "University — Year 2", "group": "University"},
    {"id": "junior", "name": "University — Year 3", "group": "University"},
    {"id": "senior", "name": "University — Year 4", "group": "University"},
    {"id": "postgrad", "name": "Postgraduate", "group": "University"},
    {"id": "self_learner", "name": "Self-learner", "group": "Other"},
]

POPULAR_SUBJECTS = [
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
    "English Language",
    "Literature",
    "Economics",
    "History",
    "Geography",
    "Accounting",
    "Business Studies",
    "Psychology",
    "Philosophy",
    "Sociology",
    "Political Science",
    "Art & Design",
    "Music Theory",
    "Statistics",
    "Engineering",
]