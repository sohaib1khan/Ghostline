"""Ghostwalk maze engine — shared by browser (Pyodide) and server replay."""

from app.ghostwalk.world import replay, run_learner_code, stars_for_lines

__all__ = ["replay", "run_learner_code", "stars_for_lines"]
