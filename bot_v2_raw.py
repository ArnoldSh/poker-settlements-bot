from __future__ import annotations

import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from poker_bot.handlers import register_handlers
from poker_bot.i18n import tr

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET_TOKEN = os.environ.get("BOT_WEBHOOK_SECRET_TOKEN")


class TelegramWebhookRuntime:
    def __init__(self) -> None:
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise RuntimeError(tr("missing_bot_token"))

        self.host = HOST
        self.port = PORT
        self.webhook_path = WEBHOOK_PATH
        self.secret_token = WEBHOOK_SECRET_TOKEN
        self.loop = asyncio.new_event_loop()
        self.loop_thread: Thread | None = None
        self.application: Application = ApplicationBuilder().token(token).build()
        register_handlers(self.application)

    async def _startup(self) -> None:
        await self.application.initialize()
        await self.application.start()

    async def _shutdown(self) -> None:
        await self.application.stop()
        await self.application.shutdown()

    async def handle_update(self, payload: dict) -> None:
        update = Update.de_json(payload, self.application.bot)
        if update is not None:
            await self.application.process_update(update)

    def start(self) -> None:
        self.loop_thread = Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()
        asyncio.run_coroutine_threadsafe(self._startup(), self.loop).result()

    def stop(self) -> None:
        asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result()
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.loop_thread is not None:
            self.loop_thread.join(timeout=5)

    def process_payload(self, payload: dict) -> None:
        asyncio.run_coroutine_threadsafe(self.handle_update(payload), self.loop).result()

    def verify_secret(self, header_value: str | None) -> bool:
        return not self.secret_token or header_value == self.secret_token

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


def make_handler(runtime: TelegramWebhookRuntime):
    class TelegramWebhookHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/healthz":
                self.send_response(404)
                self.end_headers()
                return

            self._write_json(200, {"status": tr("healthcheck_ok")})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != runtime.webhook_path:
                self.send_response(404)
                self.end_headers()
                return

            secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            print(secret_header)
            if not runtime.verify_secret(secret_header):
                self._write_json(401, {"detail": tr("webhook_secret_invalid")})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                payload = json.loads(raw_body)
            except (ValueError, json.JSONDecodeError):
                self._write_json(400, {"detail": "Invalid JSON"})
                return

            runtime.process_payload(payload)
            self._write_json(200, {"ok": True})

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _write_json(self, status_code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return TelegramWebhookHandler


def main() -> None:
    runtime = TelegramWebhookRuntime()
    runtime.start()
    server = ThreadingHTTPServer((runtime.host, runtime.port), make_handler(runtime))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.stop()


if __name__ == "__main__":
    main()
