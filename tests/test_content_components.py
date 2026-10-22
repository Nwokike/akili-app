"""Content component smoke tests — cards, states, rich content."""

from components.course_card import CourseCard, subject_color
from components.error_state import ErrorState, OfflineState
from components.loading_state import LoadingState, ProgressState
from components.module_card import ModuleCard
from components.rich_content import render_rich_content
from components.video_card import VideoCard, platform_info, youtube_thumbnail
from tests.flet_tree import walk, walk_buttons, walk_texts


def test_subject_color_cycles():
    assert subject_color(0) == subject_color(10)


def test_course_card_renders(fake_page):
    card = CourseCard({"subject": "Biology", "level": "SSS 2", "progress_pct": 40, "color_index": 0})
    texts = [t.value for t in walk_texts(card)]
    assert "Biology" in texts
    assert "40%" in texts


def test_module_card_locked_vs_unlocked():
    tapped = []
    locked = ModuleCard({"title": "M", "is_unlocked": False, "is_completed": False}, 0, on_tap=lambda m: tapped.append(m))
    unlocked = ModuleCard({"title": "M", "is_unlocked": True, "is_completed": False}, 1, on_tap=lambda m: tapped.append(m))
    assert locked.on_click is None
    assert unlocked.on_click is not None


def test_module_card_with_tap():
    seen = []
    card = ModuleCard(
        {"title": "M", "is_unlocked": True, "is_completed": False},
        0,
        None,
        on_tap=lambda m: seen.append(m),
    )
    assert card.on_click is not None


def test_loading_state_renders():
    assert list(walk(LoadingState("Preparing…")))
    assert list(walk(ProgressState("Working…")))


def test_error_state_renders():
    panel = ErrorState("Oops", "Something broke", "Try again", on_action=lambda e: None)
    assert len(list(walk_buttons(panel))) == 1


def test_offline_state_renders():
    assert list(walk(OfflineState(on_retry=lambda e: None)))


def test_youtube_thumbnail_extraction():
    assert youtube_thumbnail("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    assert youtube_thumbnail("https://youtu.be/dQw4w9WgXcQ") == "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
    assert youtube_thumbnail("https://example.com/x.mp4") == ""


def test_platform_info():
    assert platform_info("https://youtube.com/watch?v=abc")[0] == "YouTube"
    assert platform_info("https://vimeo.com/123")[0] == "Vimeo"


def test_video_card_renders(fake_page):
    card = VideoCard("Title", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert len(list(walk(card))) > 0


def test_rich_content_plain_markdown(fake_page):
    controls = render_rich_content("# Hello\n\nWorld.", fake_page)
    assert controls  # at least the markdown block


def test_rich_content_lesson_video(fake_page):
    text = "Some content.\n\n[VIDEO]: Intro - https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\nMore."
    controls = render_rich_content(text, fake_page)
    assert len(controls) >= 2  # markdown + video card + markdown


def test_rich_content_strips_latex(fake_page):
    controls = render_rich_content("The formula $$x^2$$ is here.", fake_page)
    texts = [t.value for t in walk_texts(controls[0])] if controls else []
    assert not any("$$" in t for t in texts)


def test_rich_content_empty(fake_page):
    assert render_rich_content("", fake_page) == []
