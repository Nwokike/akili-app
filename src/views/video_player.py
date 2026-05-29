import asyncio
import contextlib
import logging

import flet as ft
import flet_video as fv

from core.theme import AppColors, AppStyles

logger = logging.getLogger(__name__)


def build_video_player_view(page: ft.Page, navigate) -> ft.View:
    # Retrieve parameters from session
    video_url = page.session.get("playing_video_url") or ""
    video_title = page.session.get("playing_video_title") or "Educational Video"

    # Status & Overlay elements
    status_text = ft.Text(
        "Preparing media...",
        size=15,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_500,
        text_align=ft.TextAlign.CENTER,
    )
    loading_ring = ft.ProgressRing(width=36, height=36, stroke_width=4, color=AppColors.PRIMARY)
    overlay = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [loading_ring, ft.Container(height=16), status_text],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )

    # Speed management
    speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
    speed_idx = 2  # 1.0x
    speed_text = ft.Text("1.0x", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)

    async def cycle_speed(e):
        nonlocal speed_idx
        speed_idx = (speed_idx + 1) % len(speeds)
        rate = speeds[speed_idx]
        video.playback_rate = rate
        speed_text.value = f"{rate}x"
        video.update()
        speed_text.update()

    speed_btn = ft.Container(
        content=speed_text,
        padding=ft.Padding(10, 6, 10, 6),
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
        border_radius=AppStyles.RADIUS_SMALL,
        on_click=page.run_task(cycle_speed) if hasattr(page, "run_task") else cycle_speed,
    )

    # Back action
    is_closing = False

    async def handle_back(e=None):
        nonlocal is_closing
        if is_closing:
            return
        is_closing = True
        try:
            video.playlist = []
            await video.stop()
        except Exception:
            pass
        # Pop back to previous view
        if len(page.views) > 1:
            page.views.pop()
            page.update()
        else:
            await navigate("/tutor")

    back_btn = ft.IconButton(
        icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Back",
        on_click=lambda e: page.run_task(handle_back) if hasattr(page, "run_task") else asyncio.create_task(handle_back()),
    )

    # Safe fallback if native flet-video can't play it (like YouTube in some environments)
    async def open_external(e):
        with contextlib.suppress(Exception):
            await page.launch_url_async(video_url)

    external_btn = ft.IconButton(
        icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Open in Browser",
        on_click=open_external,
    )

    title_text = ft.Text(
        video_title,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_500,
        size=14,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # Initialize video control
    video = fv.Video(
        autoplay=True,
        expand=True,
        wakelock=True,
        filter_quality=ft.FilterQuality.MEDIUM,
        pause_upon_entering_background_mode=True,
        resume_upon_entering_foreground_mode=True,
        fill_color=ft.Colors.BLACK,
        fit=ft.BoxFit.CONTAIN,
        alignment=ft.Alignment.CENTER,
        title=video_title,
        on_load=lambda e: hide_overlay(),
        on_error=lambda e: show_error(f"Error loading stream: {e.data}"),
        controls=fv.AdaptiveVideoControls(
            # Touch/Mobile
            material=fv.MaterialVideoControls(
                visible_on_mount=True,
                display_seek_bar=True,
                seek_on_double_tap=True,
                seek_gesture=True,
                volume_gesture=True,
                brightness_gesture=True,
                speed_up_on_long_press=True,
                seek_bar_position_color=AppColors.PRIMARY,
                button_bar_button_color=ft.Colors.WHITE,
                top_button_bar=[
                    back_btn,
                    title_text,
                    fv.VideoSpacer(),
                    external_btn,
                    fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE),
                ],
                bottom_button_bar=[
                    fv.VideoPositionIndicator(text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE)),
                    fv.VideoSpacer(),
                    speed_btn,
                ],
            ),
            # Desktop/TV D-pad
            material_desktop=fv.MaterialDesktopVideoControls(
                visible_on_mount=True,
                display_seek_bar=True,
                modify_volume_on_scroll=True,
                toggle_fullscreen_on_double_press=True,
                primary_button_bar=[
                    fv.VideoSkipPreviousButton(icon_color=ft.Colors.WHITE),
                    fv.VideoPlayOrPauseButton(icon_size=36, icon_color=ft.Colors.WHITE),
                    fv.VideoSkipNextButton(icon_color=ft.Colors.WHITE),
                ],
                top_button_bar=[
                    back_btn,
                    title_text,
                    fv.VideoSpacer(),
                    external_btn,
                    fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE),
                ],
                bottom_button_bar=[
                    fv.VideoVolumeButton(slider_width=80, icon_color=ft.Colors.WHITE),
                    fv.VideoSpacer(),
                    fv.VideoPositionIndicator(text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE)),
                    fv.VideoSpacer(),
                    speed_btn,
                ],
                seek_bar_position_color=AppColors.PRIMARY,
            ),
        ),
    )

    def hide_overlay():
        overlay.visible = False
        with contextlib.suppress(Exception):
            overlay.update()

    def show_error(msg: str):
        status_text.value = f"{msg}\nTap the browser icon to watch externally."
        loading_ring.visible = False
        with contextlib.suppress(Exception):
            overlay.update()

    async def start_playback():
        logger.info("Playing video: %s", video_url)
        # Handle YouTube stream url extraction if needed (basic)
        # Note: flet-video can stream YouTube if mpv with yt-dlp is set up on desktop,
        # but otherwise it acts as raw stream player.
        try:
            video.playlist = [fv.VideoMedia(video_url)]
            video.update()
            await video.play()

            # Auto-hide overlay after 5s if on_load is not triggered (failsafe)
            await asyncio.sleep(5.0)
            if overlay.visible and loading_ring.visible:
                hide_overlay()
        except Exception as ex:
            show_error(str(ex))

    # Run playback trigger
    page.run_task(start_playback)

    return ft.View(
        route="/video_player",
        controls=[
            ft.Stack(
                [
                    ft.Container(expand=True, bgcolor=ft.Colors.BLACK),
                    video,
                    overlay,
                ],
                expand=True,
            )
        ],
        padding=0,
    )
