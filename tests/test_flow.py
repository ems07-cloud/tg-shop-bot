"""Полная покупка через настоящие обработчики бота: от /start до оплаты и смены статуса.

Подменены только Telegram (tests/fakes.py) и база (в памяти)."""
import asyncio
from types import SimpleNamespace

import pytest
from aiogram.fsm.storage.memory import MemoryStorage

from app import config, handlers_admin as admin, handlers_user as user
from app.keyboards import AdminNav, AdminOrder, AdminStatus, CartChange, Cat, Choice, Nav, Prod
from tests.fakes import Chat, FakeBot, FakePreCheckout, buttons

BUYER, ADMIN = 1001, 777


@pytest.fixture
def world(Session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})
    monkeypatch.setattr(config, "PAYMENT_PROVIDER_TOKEN", "test-provider-token")
    bot, storage = FakeBot(), MemoryStorage()
    return SimpleNamespace(bot=bot, buyer=Chat(BUYER, "Анна", bot, storage), admin=Chat(ADMIN, "Ерем", bot, storage))


def run(coro):
    return asyncio.run(coro)


def buy(w):
    """Сценарий покупателя: два пакета Эфиопии, курьер, оплата картой."""
    c = w.buyer
    run(user.start(c.message("/start"), c.state))
    run(user.catalog(c.press("☕ Каталог")))
    run(user.category(c.press("☕ Зерновой кофе"), Cat(id=1)))
    run(user.product(c.press("Эфиопия Иргачеффе"), Prod(id=1)))
    run(user.cart_change(c.press("🛒 В корзину"), CartChange(product_id=1, delta=1, view="product")))
    run(user.cart_change(c.press("➕"), CartChange(product_id=1, delta=1, view="product")))
    run(user.cart(c.press("🛒 Корзина")))
    run(user.checkout_start(c.press("✅ Оформить заказ"), c.state))
    run(user.checkout_name(c.message("Анна"), c.state))
    contact = SimpleNamespace(phone_number="79991234567")
    run(user.checkout_phone(c.message(contact=contact), c.state))
    run(user.checkout_delivery(c.press("🚚 Курьер"), Choice(field="delivery", value="courier"), c.state))
    run(user.checkout_address(c.message("ул. Тверская, 7, кв. 12, 3 этаж"), c.state))
    run(user.checkout_payment(c.press("💳 Картой сейчас"), Choice(field="payment", value="card"), c.state))
    run(user.checkout_confirm(c.press("✅ Подтвердить"), c.state))


def test_full_purchase_with_card_payment(world):
    buy(world)
    c, bot = world.buyer, world.bot

    cart = next(t for who, t, _ in c.log if who.startswith("bot") and t.startswith("🛒 <b>Корзина"))
    assert "2 × 890 ₽ = 1 780 ₽" in cart
    summary = next(t for who, t, _ in c.log if who.startswith("bot") and t.startswith("Проверьте заказ"))
    assert "К оплате: 2 080 ₽" in summary          # 2 × 890 ₽ + доставка 300 ₽
    assert c.last_bot_text().startswith("Заказ №1 оформлен")

    (invoice,) = bot.invoices
    assert invoice["payload"] == "order:1"
    assert sum(p.amount for p in invoice["prices"]) == 208000
    assert [m for m in bot.messages if m[0] == ADMIN][0][1].startswith("🆕 <b>Заказ №1</b>")

    q = FakePreCheckout(BUYER, "order:1", 208000)
    run(user.pre_checkout(q))
    assert q.result == (True, None)

    payment = SimpleNamespace(invoice_payload="order:1", telegram_payment_charge_id="tg-charge-1")
    run(user.paid(c.message(successful_payment=payment)))
    assert c.last_bot_text().startswith("Оплата получена")

    q2 = FakePreCheckout(BUYER, "order:1", 208000)        # второй раз за тот же заказ не берём
    run(user.pre_checkout(q2))
    assert q2.result[0] is False


def test_admin_moves_order_and_buyer_is_notified(world):
    buy(world)
    a = world.admin
    run(admin.admin(a.message("/admin")))
    assert "Ждут обработки: 1" in a.last_bot_text()
    run(admin.waiting(a.press("📥 Ждут обработки")))
    run(admin.order_card(a.press("№1"), AdminOrder(id=1)))
    assert ["📦 Подтвердить", "❌ Отменить"] in buttons(a.log[-1][2])
    run(admin.change_status(a.press("📦 Подтвердить"), AdminStatus(id=1, status="confirmed")))
    assert "📦 Собирается" in a.last_bot_text()
    assert (BUYER, "Заказ №1: 📦 Собирается", None) in world.bot.messages

    run(admin.export(a.press("📊 Все заказы в Excel")))
    assert a.log[-1][0] == "doc" and a.log[-1][1] == "Заказов в файле: 1"


def test_stock_limit_is_shown_to_buyer(world):
    c = world.buyer
    for _ in range(4):
        run(user.cart_change(c.press("➕"), CartChange(product_id=9, delta=1, view="product")))  # кофемолка, 4 шт.
    run(user.cart_change(c.press("➕"), CartChange(product_id=9, delta=1, view="product")))
    assert c.log[-1] == ("alert", "На складе только 4 шт.", None)


def test_bad_phone_asks_again(world):
    c = world.buyer
    run(user.checkout_phone(c.message("позвоните мне"), c.state))
    assert "Не похоже на номер" in c.last_bot_text()
