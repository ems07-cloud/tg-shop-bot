"""Подмена Telegram для сквозных тестов: обработчики вызываются как есть,
а всё, что бот «отправил», складывается в журнал переписки."""
from __future__ import annotations

from types import SimpleNamespace

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage


class FakeBot:
    def __init__(self):
        self.messages = []       # (chat_id, text, markup) — то, что бот прислал сам
        self.invoices = []

    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.messages.append((chat_id, text, reply_markup))

    async def send_invoice(self, **kw):
        self.invoices.append(kw)


class Chat:
    """Переписка одного пользователя с ботом."""

    def __init__(self, user_id: int, name: str, bot: FakeBot, storage: MemoryStorage):
        self.user_id, self.name, self.bot = user_id, name, bot
        self.log = []            # (кто, текст, клавиатура)
        self.state = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id))

    def user(self):
        return SimpleNamespace(id=self.user_id, first_name=self.name)

    def message(self, text=None, contact=None, successful_payment=None):
        if text:
            self.log.append(("me", text, None))
        elif contact:
            self.log.append(("me", "📱 " + contact.phone_number, None))
        return FakeMessage(self, text=text, contact=contact, successful_payment=successful_payment)

    def press(self, label: str):
        """Нажатие инлайн-кнопки: в журнал пишем её подпись."""
        self.log.append(("press", label, None))
        return FakeCallback(self)

    def last_bot_text(self) -> str:
        return next(t for who, t, _ in reversed(self.log) if who.startswith("bot"))


class FakeMessage:
    def __init__(self, chat: Chat, text=None, contact=None, successful_payment=None):
        self.chat, self.text, self.contact, self.successful_payment = chat, text, contact, successful_payment
        self.from_user = chat.user()
        self.bot = chat.bot

    async def answer(self, text, reply_markup=None, **kw):
        self.chat.log.append(("bot", text, reply_markup))
        return FakeMessage(self.chat)

    async def edit_text(self, text, reply_markup=None, **kw):
        self.chat.log.append(("bot-edit", text, reply_markup))

    async def answer_document(self, document, caption=None, **kw):
        self.chat.log.append(("doc", caption, document))


class FakeCallback:
    def __init__(self, chat: Chat):
        self.chat = chat
        self.from_user = chat.user()
        self.message = FakeMessage(chat)
        self.bot = chat.bot

    async def answer(self, text=None, show_alert=False, **kw):
        if text:
            self.chat.log.append(("alert" if show_alert else "toast", text, None))


class FakePreCheckout:
    def __init__(self, user_id, payload, amount):
        self.from_user = SimpleNamespace(id=user_id)
        self.invoice_payload, self.total_amount = payload, amount
        self.result = None

    async def answer(self, ok, error_message=None):
        self.result = (ok, error_message)


def buttons(markup) -> list[list[str]]:
    """Подписи кнопок клавиатуры по рядам."""
    if markup is None:
        return []
    rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []
    return [[b.text for b in row] for row in rows]
