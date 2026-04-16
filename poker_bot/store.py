from __future__ import annotations

from poker_bot.domain import Game


class InMemoryStore:
    def __init__(self) -> None:
        self.games: dict[int, Game] = {}

    def get(self, chat_id: int) -> Game:
        game = self.games.get(chat_id)
        if game is None:
            game = Game()
            self.games[chat_id] = game
        return game

    def reset(self, chat_id: int) -> None:
        self.games[chat_id] = Game()

