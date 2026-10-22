"""Settings screen — the full preferences surface.

Section order (DDGS): Appearance, Learning, AI Tutor, Web Search, banner,
Premium, Data, Study links, Troubleshooting, banner, About, banner.
Rows (Sherlock): setting_row + settings_card primitives throughout.
"""

from __future__ import annotations

import flet as ft

from components.banner_ad import build_banner_ad
from components.section_header import SectionHeader
from components.settings.sections_ai import build_ai_section
from components.settings.sections_general import build_appearance_section, build_learning_section
from components.settings.sections_mcp import MCPSection
from components.settings.sections_misc import (
    build_about_section,
    build_data_section,
    build_study_section,
    build_troubleshooting_section,
)
from components.settings.sections_premium import build_premium_section
from core import tokens


@ft.component
def SettingsScreen():
    """Full settings — appearance, learning, AI, search, premium, data, about."""
    page = ft.context.page

    sections: list[ft.Control] = [
        SectionHeader("Appearance"),
        build_appearance_section(page),
        SectionHeader("Learning"),
        build_learning_section(page),
        SectionHeader("AI Tutor"),
        build_ai_section(page),
        SectionHeader("Web Search"),
        MCPSection(),
        build_banner_ad(page),
        SectionHeader("Premium"),
        build_premium_section(page),
        SectionHeader("Data"),
        build_data_section(page),
        SectionHeader("Study"),
        build_study_section(page),
        SectionHeader("Troubleshooting"),
        build_troubleshooting_section(page),
        build_banner_ad(page),
        SectionHeader("About"),
        build_about_section(page),
        build_banner_ad(page),
        ft.Container(height=tokens.SPACE_MD),
    ]

    return ft.ListView(
        controls=sections,
        spacing=0,
        expand=True,
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_XL),
    )
