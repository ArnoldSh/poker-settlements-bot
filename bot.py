#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram bot to automate poker settlements.
- Input: for each player (Telegram @username or name), their buy-in and their chips left at the end (1 chip == 1 EUR).
- Output: set of money transfers to settle winners/losers.

This version:
- HUB auto-pick selects player with the MAX absolute net (reduces money movements).
- Adds humorous highlights of winners/losers with randomized comments per request.

Run
- Python 3.10+
- pip install python-telegram-bot==21.*
- Set environment variable BOT_TOKEN with your bot token from @BotFather.
- python bot.py

Example input line:
  @alice 100 -> 30
  bob 50 0
  @carol 80 -> 200
You can separate buy-in and out by space or "->".
"""
from __future__ import annotations
import os
import re
import random
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Tuple, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


# ---------- utils ----------
MONEY_Q = Decimal("0.01")


def d(x: str | int | float | Decimal) -> Decimal:
    if isinstance(x, Decimal):
        val = x
    else:
        s = str(x).strip().replace(",", ".")
        try:
            val = Decimal(s)
        except InvalidOperation:
            raise ValueError(f"Не могу распознать число: {x}")
    return val.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def eur(amount: Decimal) -> str:
    # Format like 1 234,56 € (using narrow no-break space)
    s = f"{amount:,.2f} €".replace(",", "_").replace(".", ",").replace("_", " ")
    return s


# ---------- domain ----------
@dataclass
class Player:
    name: str  # usually @username
    buyin: Decimal = Decimal(0)
    out: Decimal = Decimal(0)

    @property
    def net(self) -> Decimal:
        return (self.out - self.buyin).quantize(MONEY_Q)


@dataclass
class Game:
    players: Dict[str, Player] = field(default_factory=dict)

    def add_or_update(self, name: str, buyin: Decimal, out: Decimal) -> None:
        key = normalize_name(name)
        p = self.players.get(key) or Player(name=key)
        p.buyin = d(buyin)
        p.out = d(out)
        self.players[key] = p

    def remove(self, name: str) -> bool:
        return self.players.pop(normalize_name(name), None) is not None

    @property
    def total_buyin(self) -> Decimal:
        return sum((p.buyin for p in self.players.values()), Decimal(0)).quantize(MONEY_Q)

    @property
    def total_out(self) -> Decimal:
        return sum((p.out for p in self.players.values()), Decimal(0)).quantize(MONEY_Q)

    def nets(self) -> Dict[str, Decimal]:
        return {p.name: p.net for p in self.players.values()}

    def check_balance(self) -> Optional[str]:
        diff = (self.total_out - self.total_buyin).quantize(MONEY_Q)
        if diff != 0:
            return (
                "⚠️ Сумма выходов не равна сумме бай-инов.\n"
                f"Бай-ины: {eur(self.total_buyin)}, Выходы: {eur(self.total_out)}.\n"
                "Проверьте ввод (числа и игроков)."
            )
        return None


@dataclass
class Transfer:
    frm: str
    to: str
    amount: Decimal

    def __str__(self) -> str:
        return f"{self.frm} → {self.to}: {eur(self.amount)}"


# ---------- settlement algorithms ----------

def settle_direct(nets: Dict[str, Decimal]) -> List[Transfer]:
    creditors: List[Tuple[str, Decimal]] = []  # who should receive (net > 0)
    debtors: List[Tuple[str, Decimal]] = []    # who should pay (net < 0) as positive amount
    for name, val in nets.items():
        if val > 0:
            creditors.append((name, val))
        elif val < 0:
            debtors.append((name, -val))
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    i = j = 0
    transfers: List[Transfer] = []
    while i < len(debtors) and j < len(creditors):
        d_name, d_amt = debtors[i]
        c_name, c_amt = creditors[j]
        pay = min(d_amt, c_amt).quantize(MONEY_Q)
        if pay > 0:
            transfers.append(Transfer(d_name, c_name, pay))
            d_amt = (d_amt - pay).quantize(MONEY_Q)
            c_amt = (c_amt - pay).quantize(MONEY_Q)
        if d_amt == 0:
            i += 1
        else:
            debtors[i] = (d_name, d_amt)
        if c_amt == 0:
            j += 1
        else:
            creditors[j] = (c_name, c_amt)
    return transfers


def pick_hub_auto(nets: Dict[str, Decimal]) -> str:
    """Pick player with MAX absolute net (if tie, lexicographically)."""
    return max(nets.items(), key=lambda kv: (abs(kv[1]), kv[0]))[0]


def settle_hub(nets: Dict[str, Decimal], hub: Optional[str] = None) -> Tuple[str, List[Transfer]]:
    if not nets:
        return ("", [])
    hub_name = hub or pick_hub_auto(nets)
    if hub_name not in nets:
        raise ValueError("Указанный hub не найден среди игроков")
    transfers: List[Transfer] = []
    for name, net in nets.items():
        if name == hub_name or net == 0:
            continue
        if net < 0:  # debtor -> hub
            transfers.append(Transfer(name, hub_name, -net))
        else:  # hub -> winner
            transfers.append(Transfer(hub_name, name, net))
    return (hub_name, transfers)


# ---------- parsing ----------
LINE_RE = re.compile(r"^\s*(?P<name>@?\w+)\s+(?P<buy>[-+]?\d+[\d\.,]*)\s*(?:->|—|\s)\s*(?P<out>[-+]?\d+[\d\.,]*)\s*$")


def normalize_name(name: str) -> str:
    x = name.strip()
    if not x:
        raise ValueError("пустое имя")
    if not x.startswith("@"):
        x = "@" + x
    return x


def parse_line(text: str) -> Tuple[str, Decimal, Decimal]:
    m = LINE_RE.match(text)
    if not m:
        parts = text.strip().split()
        if len(parts) == 3:
            name, buy, out = parts
        else:
            raise ValueError(
                "Строка не распознана. Формат: @user <buyin> -> <out> (или три значения через пробел)."
            )
    else:
        name, buy, out = m.group("name", "buy", "out")
    return normalize_name(name), d(buy), d(out)


# ---------- in-memory store per chat ----------
class InMemoryStore:
    def __init__(self):
        self.games: Dict[int, Game] = {}

    def get(self, chat_id: int) -> Game:
        if chat_id not in self.games:
            self.games[chat_id] = Game()
        return self.games[chat_id]

    def reset(self, chat_id: int) -> None:
        self.games[chat_id] = Game()


STORE = InMemoryStore()


# ---------- fun commentary ----------
W_BIG_COMMENTS = [
    "волк с Макариу стрит 💸",
    "возможно потерял друзей, но не похер ли? 💼",
    "может хотя бы купишь нам пива?! 😈",
    "не знает, куда ему тратить наш кеш! 🏴‍☠️",
    "теперь у него будут проблемы с налоговой 😎",
    "так, с этим больше не играем 💀",
    "стэк как на дрожжах! 💸",
    "поздравляем, но не от всего сердца 💔",
    "сегодня пьёт за счёт стола 🥂",
    "это просто ограбление 🚨",
]

W_SMALL_COMMENTS = [
    "не проиграл — и то праздник 🎈",
    "скромно, но в плюс — зачёт ✅",
    "микро-ап, но приятно 😉",
    "чай на сдачу — твой ☕",
    "держишь баланс — дзен мастер 🧘",
    "тихо зашёл, тихо в плюс вышел 🐾",
    "стек не вырос, но и не упал — аккуратист ✂️",
    "+копеечка, зато стабильно 💁",
    "без фанатизма, но по делу 🧮",
    "мелочь, а приятно 💫",
]

L_BIG_COMMENTS = [
    "unlucky bro - повезёт в другой раз 🥲",
    "денег нет, но вы держитесь 🤜🤛",
    "поддержим товарища 🫂",
    "мы никому не расскажем 🤫",
    "пора сходить в церковь 🕯️⛪",
    "яйца стальные, карманы - пустые 📉",
    "зато истории будут 📖",
    "если что — мы тебя всё равно любим ❤️",
    "деньги - не главное 🫶",
    "мы с тобой, даже если карты против ❤️",
]

L_SMALL_COMMENTS = [
    "знает меру — красавчик 👍",
    "знает, когда остановиться 🛑",
    "минимизировал урон — капитан экономии ⚓",
    "отступил, чтоб вернуться и победить 🧭",
    "потерял мало, сохранил много 🛡️",
    "затерпел, но настрой боевой 💪",
    "чек-колл дисциплина засчитана ✅",
    "банку помахал, а кошелёк спас 💼",
    "тоненько прошёл по краю 🎯",
    "разумный луз это всегда уважаемо 🤝",
]


def build_highlights(nets: Dict[str, Decimal]) -> str:
    winners = [(n, v) for n, v in nets.items() if v > 0]
    losers = [(n, v) for n, v in nets.items() if v < 0]
    if not winners and not losers:
        return "Никто ничего не выиграл и не проиграл — магия равновесия. ✨"

    lines: List[str] = ["<b>🏆 Итоги</b>"]
    if winners:
        bw_name, bw_val = max(winners, key=lambda x: x[1])
        sw_name, sw_val = min(winners, key=lambda x: x[1])
        lines.append(f"🥇 {bw_name} {eur(bw_val)} — {random.choice(W_BIG_COMMENTS)}")
        if sw_name != bw_name:
            lines.append(f"🟢 {sw_name} {eur(sw_val)} — {random.choice(W_SMALL_COMMENTS)}")
    if losers:
        bl_name, bl_val = min(losers, key=lambda x: x[1])  # most negative
        sl_name, sl_val = max(losers, key=lambda x: x[1])  # closest to 0 (still negative)
        lines.append(f"🥄 {bl_name} {eur(-bl_val)} в минус — {random.choice(L_BIG_COMMENTS)}")
        if sl_name != bl_name:
            lines.append(f"🟠 {sl_name} {eur(-sl_val)} в минус — {random.choice(L_SMALL_COMMENTS)}")

    others = [n for n in nets.keys() if n not in {locals().get('bw_name', ''), locals().get('sw_name', ''), locals().get('bl_name', ''), locals().get('sl_name', '')}]
    if others:
        rest = sorted(((n, nets[n]) for n in others), key=lambda x: x[1], reverse=True)
        chunk = []
        for n, v in rest:
            tag = "+" if v > 0 else ("0" if v == 0 else "-")
            chunk.append(f"{n} {eur(v if v>=0 else -v)} ({'плюс' if tag=='+' else 'минус' if tag=='-' else 'ноль'})")
        lines.append("Прочие: " + ", ".join(chunk))

    return "\n".join(lines)


# ---------- bot commands ----------
HELP_TEXT = (
    """\
<b>Бот расчёта взаиморасчётов для покера</b>

Команды:
/start — краткая справка
/newgame — очистить текущий список игроков для этого чата
/add &lt;строка&gt; — добавить/обновить игрока одной строкой. Пример:\n  <code>/add @ivan 100 -> 40</code>
/addblock — вставьте несколько строк (по одной на игрока) после команды.
/list — показать текущую таблицу
/calc [direct|hub] [@hub] — посчитать взаиморасчёты\n  • <i>direct</i>: минимальное количество переводов между всеми\n  • <i>hub</i>: все должники платят одному игроку (если не указать — игрок с максимальной |разницей|), он платит победителям
/remove @user — удалить игрока

Правила:
• 1 фишка = 1 € (конверсия не нужна).
• Числа можно писать с точкой или запятой.
• Имена автоматически приводятся к формату @username.
"""
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я посчитаю, кто кому и сколько переводит по итогам игры.\n"
        "Сначала добавьте игроков: /add @user 100 -> 35 или /addblock чтобы добавить сразу несколько записей\n"
        "Потом: /calc direct  — или  /calc hub  (можно /calc hub @user)\n"
	"Чтобы удалить запись: /remove @user\n"
	"Можно посмотреть таблицу с балансом: /list\n"
	"Сбросить последние расчеты и завести новый стол: /newgame\n",
        parse_mode=ParseMode.HTML,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    STORE.reset(chat_id)
    await update.message.reply_text("Новый стол создан. Вводите игроков через /add или /addblock.")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = STORE.get(chat_id)
    if not context.args:
        await update.message.reply_text(
            "Использование: /add @user buyin -> out   (пример: /add @pete 100 -> 40)"
        )
        return
    line = " ".join(context.args)
    try:
        name, buy, out = parse_line(line)
        game.add_or_update(name, buy, out)
        await update.message.reply_text(f"OK: {name} — бай-ин {eur(buy)}, выход {eur(out)}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def addblock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = STORE.get(chat_id)
    text = update.message.text
    lines = text.split("\n", 1)
    if len(lines) == 1:
        await update.message.reply_text(
            "Отправьте команду так: \n<code>/addblock\n@ivan 100 -> 30\n@anna 50 0\n@petr 80 -> 200</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    block = lines[1]
    added = []
    errors = []
    for raw in block.splitlines():
        if not raw.strip():
            continue
        try:
            name, buy, out = parse_line(raw)
            game.add_or_update(name, buy, out)
            added.append(name)
        except Exception as e:
            errors.append(f"{raw} → {e}")
    msg = "Добавлены: " + (", ".join(added) if added else "—")
    if errors:
        msg += "\nОшибки:\n" + "\n".join(errors)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = STORE.get(chat_id)
    if not context.args:
        await update.message.reply_text("Использование: /remove @user")
        return
    name = normalize_name(context.args[0])
    ok = game.remove(name)
    await update.message.reply_text("Удалён" if ok else "Игрок не найден")


def render_table(game: Game) -> str:
    if not game.players:
        return "Список игроков пуст."
    head = "<b>Игрок</b> | <b>Бай-ин</b> | <b>Выход</b> | <b>Итог</b>\n" + ("—" * 30)
    lines = []
    for p in sorted(game.players.values(), key=lambda x: x.name.lower()):
        lines.append(
            f"{p.name} | {eur(p.buyin)} | {eur(p.out)} | <b>{eur(p.net)}</b>"
        )
    totals = f"Σ | {eur(game.total_buyin)} | {eur(game.total_out)} | <b>{eur(game.total_out - game.total_buyin)}</b>"
    return head + "\n".join(lines) + "\n" + ("—" * 30) + "\n" + totals


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = STORE.get(chat_id)
    await update.message.reply_text(render_table(game), parse_mode=ParseMode.HTML)


async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = STORE.get(chat_id)
    if not game.players:
        await update.message.reply_text("Нет данных. Сначала добавьте игроков через /add или /addblock.")
        return
    err = game.check_balance()
    if err:
        await update.message.reply_text(err, parse_mode=ParseMode.HTML)
        return

    mode = "direct"
    hub_name: Optional[str] = None
    args = [a for a in context.args if a]
    if args:
        mode = args[0].lower()
        if len(args) > 1:
            hub_name = normalize_name(args[1])
    nets = game.nets()

    # fun highlights every run
    highlights = build_highlights(nets)

    if mode == "hub":
        hub, transfers = settle_hub(nets, hub_name)
        header = f"Режим: HUB. Хаб: <b>{hub}</b> (автовыбор — максимальная |разница|)"
    else:
        transfers = settle_direct(nets)
        header = "Режим: DIRECT (минимум переводов)"

    if not transfers:
        await update.message.reply_text(highlights + "\n\nВсе и так в нуле — переводов не требуется.", parse_mode=ParseMode.HTML)
        return

    total = sum((t.amount for t in transfers), Decimal(0)).quantize(MONEY_Q)
    lines = [f"{i+1}. {str(t)}" for i, t in enumerate(transfers)]
    msg = (
        header
        + "\n\n"
        + highlights
        + "\n\n<b>Переводы:</b>\n"
        + "\n".join(lines)
        + "\n\n"
        + f"Всего движений денег: {len(transfers)}; Общая сумма по всем переводам: {eur(total)}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Установите переменную окружения BOT_TOKEN c токеном @BotFather")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("addblock", addblock))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("calc", calc))

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
