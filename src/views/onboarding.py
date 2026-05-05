import json
import re
import flet as ft

from core.constants import COUNTRIES, SYSTEM_TEMPLATES
from core.state import state
from core.theme import AppColors, AppStyles
from database.manager import db_manager
from services.ai_service import ai_service


def build_onboarding_view(page: ft.Page, navigate) -> ft.View:
    # State for selection
    selection = {
        "country": "Nigeria",
        "system": "WAEC (West African)",
        "level": ""
    }

    # UI Components
    name_field = ft.TextField(
        label="Full Name",
        hint_text="e.g. John Sarki",
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
        text_size=16,
    )

    error_text = ft.Text("", color=AppColors.ERROR, size=13)
    status_text = ft.Text("Choose your country to see levels", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    loading_ring = ft.ProgressRing(width=20, height=20, visible=False, stroke_width=2)
    
    level_list = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=250)

    async def _detect_system(country_name: str):
        status_text.value = f"Personalizing for {country_name}..."
        loading_ring.visible = True
        level_list.controls.clear()
        page.update()

        prompt = (
            f"Identify the educational system for {country_name}. "
            "Return JSON with: 'system_name' (str), 'levels' (list of strings)."
        )
        
        try:
            response = await ai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Return ONLY valid JSON. Be accurate."
            )
            data = _extract_json(response.get("content", ""))
            
            if data and "levels" in data:
                selection["system"] = data.get("system_name", "Local System")
                status_text.value = f"Detected: {selection['system']}"
                
                for lvl in data["levels"]:
                    level_list.controls.append(
                        ft.Container(
                            content=ft.Row([ft.Text(lvl, size=15)]),
                            padding=ft.Padding(16, 12, 16, 12),
                            border_radius=AppStyles.RADIUS_SMALL,
                            on_click=lambda e, v=lvl: _select_level(v),
                            ink=True,
                            data=lvl
                        )
                    )
            else:
                raise Exception("Invalid data")
        except:
            status_text.value = "Using standard Grade-based system"
            for lvl in SYSTEM_TEMPLATES["K12"]["levels"]:
                level_list.controls.append(
                    ft.Container(
                        content=ft.Row([ft.Text(lvl, size=15)]),
                        padding=ft.Padding(16, 12, 16, 12),
                        border_radius=AppStyles.RADIUS_SMALL,
                        on_click=lambda e, v=lvl: _select_level(v),
                        ink=True,
                        data=lvl
                    )
                )
        finally:
            loading_ring.visible = False
            page.update()

    def _select_level(val: str):
        selection["level"] = val
        for c in level_list.controls:
            is_sel = c.data == val
            c.bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY) if is_sel else ft.Colors.TRANSPARENT
            c.border = ft.Border.all(2, AppColors.PRIMARY) if is_sel else None
        page.update()

    def _on_country_change(e):
        country = country_dropdown.value
        selection["country"] = country
        page.run_task(_detect_system, country)

    country_dropdown = ft.Dropdown(
        label="Your Country",
        options=[ft.dropdown.Option(c) for c in COUNTRIES],
        value="Nigeria",
        border_radius=AppStyles.RADIUS,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_color=ft.Colors.TRANSPARENT,
    )
    country_dropdown.on_change = _on_country_change

    async def _on_complete(e):
        name = name_field.value.strip()
        country = selection["country"]
        level = selection["level"]
        
        if not name or not level:
            error_text.value = "Please enter your name and select a level"
            page.update()
            return

        state.user_name = name
        state.country = country
        state.education_level = level
        state.education_system = selection["system"]
        state.is_onboarded = True
        
        await db_manager.save_profile(name, level)
        await navigate("/dashboard")

    # Initial detection
    page.run_task(_detect_system, "Nigeria")

    return ft.View(
        route="/onboarding",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=ft.Column([
                        ft.Container(height=20),
                        ft.Image(src="/icon.png", width=64, height=64),
                        ft.Text("Personalize Akili", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text("Tell us about your learning journey.", size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Container(height=20),
                        name_field,
                        ft.Container(height=10),
                        country_dropdown,
                        ft.Container(height=20),
                        ft.Row([loading_ring, status_text], alignment=ft.MainAxisAlignment.START),
                        ft.Container(
                            content=level_list,
                            border_radius=AppStyles.RADIUS_SMALL,
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                            padding=5,
                        ),
                        error_text,
                        ft.Container(height=10),
                        ft.FilledButton(
                            "Get Started",
                            on_click=lambda e: page.run_task(_on_complete, e),
                            style=ft.ButtonStyle(
                                bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=AppStyles.RADIUS),
                                padding=24,
                            ),
                            width=float("inf"),
                        ),
                        ft.Container(height=40),
                    ], scroll=ft.ScrollMode.AUTO, spacing=10),
                    padding=20,
                ),
            )
        ],
        bgcolor=ft.Colors.SURFACE,
    )

def _extract_json(text: str) -> dict | None:
    if not text: return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try: return json.loads(text)
    except: pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try: return json.loads(match.group(0))
        except: pass
    return None
