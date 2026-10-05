"""Логика магазина без Telegram: каталог, корзина, заказы, доставка, статусы.

Обработчики бота только вызывают эти функции — так всё важное проверяется тестами.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .models import CartItem, Category, Delivery, Order, OrderItem, OrderStatus, Payment, Product


class ShopError(Exception):
    """Ошибка, текст которой можно показать покупателю."""


# ---------- каталог ----------

def categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.sort, Category.id)))


def products_in(session: Session, category_id: int) -> list[Product]:
    return list(session.scalars(
        select(Product).where(Product.category_id == category_id, Product.is_active.is_(True))
        .order_by(Product.id)))


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None or not product.is_active:
        raise ShopError("Этого товара больше нет в каталоге.")
    return product


# ---------- корзина ----------

def cart_items(session: Session, user_id: int) -> list[CartItem]:
    return list(session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id)))


def cart_qty(session: Session, user_id: int, product_id: int) -> int:
    item = session.scalar(select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    return item.qty if item else 0


def change_cart(session: Session, user_id: int, product_id: int, delta: int) -> int:
    """Добавить (delta > 0) или убрать (delta < 0) товар. Возвращает новое количество."""
    product = get_product(session, product_id)
    item = session.scalar(select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    new_qty = (item.qty if item else 0) + delta
    if new_qty > product.stock:
        raise ShopError(f"На складе только {product.stock} шт.")
    if new_qty <= 0:
        if item:
            session.delete(item)
        session.flush()
        return 0
    if item:
        item.qty = new_qty
    else:
        session.add(CartItem(user_id=user_id, product_id=product_id, qty=new_qty))
    session.flush()
    return new_qty


def clear_cart(session: Session, user_id: int) -> None:
    for item in cart_items(session, user_id):
        session.delete(item)
    session.flush()


def cart_total(items: list[CartItem]) -> int:
    return sum(i.product.price * i.qty for i in items)


def delivery_price(items_total: int, delivery: Delivery) -> int:
    if delivery == Delivery.PICKUP or items_total >= config.FREE_DELIVERY_FROM:
        return 0
    return config.DELIVERY_PRICE


# ---------- контакты ----------

def normalize_phone(raw: str) -> str:
    """+7 999 123-45-67, 8(999)1234567, 9991234567 → +79991234567."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    raise ShopError("Не похоже на номер телефона. Пример: +7 999 123-45-67")


def clean_name(raw: str) -> str:
    name = " ".join((raw or "").split())
    if not 2 <= len(name) <= 60:
        raise ShopError("Напишите имя — от 2 до 60 символов.")
    return name


# ---------- заказы ----------

@dataclass
class Checkout:
    name: str
    phone: str
    delivery: Delivery
    address: str
    payment: Payment


def create_order(session: Session, user_id: int, checkout: Checkout) -> Order:
    """Заказ из корзины: проверяем остатки, списываем их, фиксируем цены, чистим корзину."""
    items = cart_items(session, user_id)
    if not items:
        raise ShopError("Корзина пуста.")
    for item in items:
        if not item.product.is_active or item.qty > item.product.stock:
            raise ShopError(f"«{item.product.title}»: на складе {item.product.stock} шт., "
                            f"а в корзине {item.qty}. Поправьте корзину.")
    if checkout.delivery == Delivery.COURIER and len(checkout.address.strip()) < 5:
        raise ShopError("Нужен адрес доставки.")

    items_total = cart_total(items)
    order = Order(
        user_id=user_id,
        customer_name=checkout.name,
        phone=checkout.phone,
        delivery=checkout.delivery.value,
        address=checkout.address.strip() if checkout.delivery == Delivery.COURIER else config.PICKUP_ADDRESS,
        payment=checkout.payment.value,
        items_total=items_total,
        delivery_price=delivery_price(items_total, checkout.delivery),
        status=OrderStatus.NEW.value,
    )
    for item in items:
        order.items.append(OrderItem(product_id=item.product_id, title=item.product.title,
                                     price=item.product.price, qty=item.qty))
        item.product.stock -= item.qty
    session.add(order)
    clear_cart(session, user_id)
    session.flush()
    return order


# куда можно перевести заказ из текущего статуса
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.PAID, OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DONE},
    OrderStatus.DONE: set(),
    OrderStatus.CANCELLED: set(),
}


def set_status(session: Session, order_id: int, new: OrderStatus) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise ShopError("Заказ не найден.")
    current = OrderStatus(order.status)
    if new not in TRANSITIONS[current]:
        raise ShopError(f"Нельзя перевести заказ из «{current.value}» в «{new.value}».")
    if new == OrderStatus.CANCELLED:              # отмена возвращает товар на склад
        for item in order.items:
            product = session.get(Product, item.product_id)
            if product:
                product.stock += item.qty
    order.status = new.value
    session.flush()
    return order


def mark_paid(session: Session, order_id: int, charge_id: str) -> Order:
    order = set_status(session, order_id, OrderStatus.PAID)
    order.paid_at = datetime.now()
    order.charge_id = charge_id
    session.flush()
    return order


def can_pay(session: Session, order_id: int, user_id: int, amount: int) -> bool:
    """Проверка перед списанием денег (pre_checkout): заказ свой, не оплачен, сумма та же."""
    order = session.get(Order, order_id)
    return bool(order and order.user_id == user_id and order.status == OrderStatus.NEW.value
                and order.payment == Payment.CARD.value and order.total == amount)


def user_orders(session: Session, user_id: int, limit: int = 10) -> list[Order]:
    return list(session.scalars(select(Order).where(Order.user_id == user_id)
                                .order_by(Order.id.desc()).limit(limit)))


def orders_by_status(session: Session, statuses: list[OrderStatus]) -> list[Order]:
    return list(session.scalars(select(Order).where(Order.status.in_([s.value for s in statuses]))
                                .order_by(Order.id)))


def all_orders(session: Session) -> list[Order]:
    return list(session.scalars(select(Order).order_by(Order.id)))


def stats_today(session: Session) -> dict:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = [o for o in session.scalars(select(Order).where(Order.created_at >= start))
             if o.status != OrderStatus.CANCELLED.value]
    waiting = session.scalar(select(func.count(Order.id)).where(
        Order.status.in_([OrderStatus.NEW.value, OrderStatus.PAID.value]))) or 0
    return {"orders": len(today), "revenue": sum(o.total for o in today), "waiting": waiting}
