"""AppState context — exposes the global observable to the component tree.

Ported from Sherlock's state pattern (the house standard).
"""

import flet as ft

from core.state import state

AppStateCtx = ft.create_context(state)
