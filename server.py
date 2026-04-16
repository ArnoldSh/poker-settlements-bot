import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# --- Настройки ---
HOST = "0.0.0.0"
PORT = 8080
TOKEN = os.environ.get("BOT_TOKEN")

# --- Функция для отправки сообщения в Telegram ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Ошибка при отправке сообщения:", e)

# --- HTTP-сервер для webhook ---
class TelegramHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        data = json.loads(body)
        if self.path == "/webhook":
            # --- Извлекаем chat_id и текст сообщения ---
            message = data.get("message")
            if message:
                chat_id = message["chat"]["id"]
                user_text = message.get("text", "")

                # --- Логика ответа ---
                if user_text == "/start":
                    send_message(chat_id, "Привет! Я бот через webhook.")
                else:
                    send_message(chat_id, f"Вы написали: {user_text}")

            # --- Ответ Telegram что всё ок ---
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()
        print(data)

# --- Запуск сервера ---
def run():
    server = HTTPServer((HOST, PORT), TelegramHandler)
    print(f"Сервер запущен на http://{HOST}:{PORT}/webhook")
    server.serve_forever()

if __name__ == "__main__":
    run()