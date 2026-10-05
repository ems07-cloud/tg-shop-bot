"""Клавиатуры и данные кнопок."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import CartItem, Category, Delivery, OrderStatus, Payment, Product
from .services import TRANSITIONS
from .texts import STATUS, rub


class Nav(CallbackData, prefix="nav"):
    to: str                      # menu | catalog | cart | orders


class Cat(CallbackData, prefix="cat"):
    id: int


class Prod(CallbackData, prefix="prod"):
    id: int


class CartChange(CallbackData, prefix="cc"):
    product_id: int
    delta: int
    view: str                    # product | cart — где перерисовать


class Choice(CallbackData, prefix="ch"):
    field: str                   # delivery | payment | confirm
    value: str


class AdminOrder(CallbackData, prefix="ao"):
    id: int


class AdminStatus(CallbackData, prefix="as"):
    id: int
    status: str


class AdminNav(CallbackData, prefix="an"):
    to: str                      # waiting | export | dashboard


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="☕ Каталог", callback_data=Nav(to="catalog"))
    kb.button(text="🛒 Корзина", callback_data=Nav(to="cart"))
    kb.button(text="📋 Мои заказы", callback_data=Nav(to="orders"))
    kb.adjust(2, 1)
    return kb.as_markup()


def categories(cats: list[Category]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=f"{c.emoji} {c.title}".strip(), callback_data=Cat(id=c.id))
    kb.button(text="🛒 Корзина", callback_data=Nav(to="cart"))
    kb.adjust(1)
    return kb.as_markup()


def products(items: list[Product]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in items:
        mark = "" if p.stock > 0 else " (нет)"
        kb.button(text=f"{p.title} — {rub(p.price)}{mark}", callback_data=Prod(id=p.id))
    kb.button(text="⬅️ К разделам", callback_data=Nav(to="catalog"))
    kb.adjust(1)
    return kb.as_markup()


def product(p: Product, in_cart: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if in_cart:
        kb.button(text="➖", callback_data=CartChange(product_id=p.id, delta=-1, view="product"))
        kb.button(text=f"{in_cart} шт.", callback_data=Nav(to="cart"))
        kb.button(text="➕", callback_data=CartChange(product_id=p.id, delta=1, view="product"))
    elif p.stock > 0:
        kb.button(text="🛒 В корзину", callback_data=CartChange(product_id=p.id, delta=1, view="product"))
    kb.button(text="⬅️ Назад", callback_data=Cat(id=p.category_id))
    kb.button(text="🛒 Корзина", callback_data=Nav(to="cart"))
    kb.adjust(3 if in_cart else 1, 2)
    return kb.as_markup()


def cart(items: list[CartItem]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    sizes = []
    for i in items:
        kb.button(text="➖", callback_data=CartChange(product_id=i.product_id, delta=-1, view="cart"))
        kb.button(text=f"{i.product.title[:22]} · {i.qty}", callback_data=Prod(id=i.product_id))
        kb.button(text="➕", callback_data=CartChange(product_id=i.product_id, delta=1, view="cart"))
        sizes.append(3)
    if items:
        kb.button(text="✅ Оформить заказ", callback_data=Choice(field="checkout", value="start"))
        sizes.append(1)
    kb.button(text="☕ Каталог", callback_data=Nav(to="catalog"))
    sizes.append(1)
    kb.adjust(*sizes)
    return kb.as_markup()


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
                               resize_keyboard=True, one_time_keyboard=True)


def delivery() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚚 Курьер", callback_data=Choice(field="delivery", value=Delivery.COURIER.value))
    kb.button(text="🏠 Самовывоз", callback_data=Choice(field="delivery", value=Delivery.PICKUP.value))
    kb.adjust(2)
    return kb.as_markup()


def payment(card_enabled: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if card_enabled:
        kb.button(text="💳 Картой сейчас", callback_data=Choice(field="payment", value=Payment.CARD.value))
    kb.button(text="💵 При получении", callback_data=Choice(field="payment", value=Payment.CASH.value))
    kb.adjust(1)
    return kb.as_markup()


def confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=Choice(field="confirm", value="yes"))
    kb.button(text="✏️ Изменить корзину", callback_data=Nav(to="cart"))
    kb.adjust(1)
    return kb.as_markup()


def admin_dashboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📥 Ждут обработки", callback_data=AdminNav(to="waiting"))
    kb.button(text="📊 Все заказы в Excel", callback_data=AdminNav(to="export"))
    kb.adjust(1)
    return kb.as_markup()


def admin_orders(orders) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.button(text=f"№{o.id} · {rub(o.total)} · {STATUS[o.status]}", callback_data=AdminOrder(id=o.id))
    kb.button(text="⬅️ Админка", callback_data=AdminNav(to="dashboard"))
    kb.adjust(1)
    return kb.as_markup()


ADMIN_ACTIONS = {
    OrderStatus.CONFIRMED: "📦 Подтвердить",
    OrderStatus.SHIPPED: "🚚 Отправлен",
    OrderStatus.DONE: "✅ Получен",
    OrderStatus.CANCELLED: "❌ Отменить",
}


def admin_order(order) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    allowed = TRANSITIONS[OrderStatus(order.status)]
    for status, label in ADMIN_ACTIONS.items():
        if status in allowed:
            kb.button(text=label, callback_data=AdminStatus(id=order.id, status=status.value))
    kb.button(text="⬅️ К списку", callback_data=AdminNav(to="waiting"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()
