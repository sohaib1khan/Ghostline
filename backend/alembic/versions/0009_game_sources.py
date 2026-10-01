"""Allow new practice game source ids."""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_game_sources"
down_revision: str | None = "0008_practice_duration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_SOURCES = (
    "lesson",
    "speed_drill",
    "bug_hunt",
    "command_roulette",
    "fill_frenzy",
    "ghost_race",
    "code_hangman",
    "codele",
    "memory_match",
    "code_crossword",
    "tic_tac_toe",
    "syntax_snake",
    "predict_output",
    "code_scramble",
    "query_detective",
    "boss_battle",
)

OLD_SOURCES = (
    "lesson",
    "speed_drill",
    "bug_hunt",
    "command_roulette",
    "fill_frenzy",
)


def upgrade() -> None:
    op.drop_constraint("ck_practice_events_source", "practice_events", type_="check")
    listed = ", ".join(f"'{item}'" for item in NEW_SOURCES)
    op.create_check_constraint(
        "ck_practice_events_source",
        "practice_events",
        f"source in ({listed})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_practice_events_source", "practice_events", type_="check")
    listed = ", ".join(f"'{item}'" for item in OLD_SOURCES)
    op.create_check_constraint(
        "ck_practice_events_source",
        "practice_events",
        f"source in ({listed})",
    )
