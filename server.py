from __future__ import annotations

import uvicorn

from poker_bot.config import load_settings
from poker_bot.logging_utils import configure_logging


def main() -> None:
    configure_logging()
    settings = load_settings()
    uvicorn.run("poker_bot.web:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
