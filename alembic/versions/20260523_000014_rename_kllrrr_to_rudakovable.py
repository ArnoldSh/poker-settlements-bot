"""rename kllrrr to rudakovable

Revision ID: 20260523_000014
Revises: 20260509_000013
Create Date: 2026-05-23 00:00:14
"""
from __future__ import annotations

from alembic import op


revision = "20260523_000014"
down_revision = "20260509_000013"
branch_labels = None
depends_on = None

OLD_NAME = "@kllrrr"
NEW_NAME = "@rudakovable"


def upgrade() -> None:
    _rename_player_everywhere(source_name=OLD_NAME, target_name=NEW_NAME)


def downgrade() -> None:
    _rename_player_everywhere(source_name=NEW_NAME, target_name=OLD_NAME)


def _rename_player_everywhere(*, source_name: str, target_name: str) -> None:
    source = _quote(source_name)
    target = _quote(target_name)

    op.execute(
        f"""
        UPDATE game_buyin_entries
        SET player_name = '{target}'
        WHERE player_name = '{source}'
        """
    )

    op.execute(
        f"""
        UPDATE game_players
        SET
            buyin = buyin + (
                SELECT source_row.buyin
                FROM game_players AS source_row
                WHERE source_row.game_id = game_players.game_id
                  AND source_row.player_name = '{source}'
            ),
            out = out + (
                SELECT source_row.out
                FROM game_players AS source_row
                WHERE source_row.game_id = game_players.game_id
                  AND source_row.player_name = '{source}'
            )
        WHERE player_name = '{target}'
          AND EXISTS (
              SELECT 1
              FROM game_players AS source_row
              WHERE source_row.game_id = game_players.game_id
                AND source_row.player_name = '{source}'
          )
        """
    )

    op.execute(
        f"""
        DELETE FROM game_players
        WHERE player_name = '{source}'
          AND EXISTS (
              SELECT 1
              FROM game_players AS target_row
              WHERE target_row.game_id = game_players.game_id
                AND target_row.player_name = '{target}'
          )
        """
    )

    op.execute(
        f"""
        UPDATE game_players
        SET player_name = '{target}'
        WHERE player_name = '{source}'
        """
    )


def _quote(value: str) -> str:
    return value.replace("'", "''")
