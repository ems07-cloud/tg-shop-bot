"""Все тексты бота в одном месте."""
from __future__ import annotations

from . import config
from .models import CartItem, Delivery, Order, OrderStatus, Payment, Product

STATUS = {
    OrderStatus.NEW.value: "🆕 Новый",
    OrderStatus.PAID.value: "💳 Оплачен",
    OrderStatus.CONFIRMED.value: "📦 Собирается",
    OrderStatus.SHIPPED.value: "🚚 В пути / готов к выдаче",
    OrderStatus.DONE.value: "✅ Получен",
    OrderStatus.CANCELLED.value: "❌ Отменён",
}
DELIVERY = {Delivery.COURIER.value: "Курьер", Delivery.PICKUP.value: "Самовывоз"}
PAYMENT = {Payment.CARD.value: "Картой в Telegram", Payment.CASH.value: "При получении"}


def rub(kop: int) -> str:
    rubles, k = divmod(kop, 100)
    text = f"{rubles:,}".replace(",", " ")
    return f"{text},{k:02d} ₽" if k else f"{text} ₽"


def welcome(name: str) -> str:
    return (f"Привет, {name}! Это {config.SHOP_NAME} ☕\n\n"
            "Свежая обжарка каждую неделю, доставка по Москве или самовывоз.\n"
            f"Доставка бесплатно от {rub(config.FREE_DELIVERY_FROM)}.")


def product_card(p: Product, in_cart: int) -> str:
    stock = f"В наличии: {p.stock} шт." if p.stock > 0 else "Нет в наличии"
    lines = [f"<b>{p.title}</b>", "", p.description, "", f"Цена: <b>{rub(p.price)}</b>", stock]
    if in_cart:
        lines.append(f"🛒 В корзине: {in_cart} шт.")
    return "\n".join(lines)


def cart(items: list[CartItem]) -> str:
    if not items:
        return "🛒 Корзина пуста.\nЗагляните в каталог — там свежая обжарка."
    lines = ["🛒 <b>Корзина</b>", ""]
    total = 0
    for i in items:
        s = i.product.price * i.qty
        total += s
        lines.append(f"• {i.product.title}\n   {i.qty} × {rub(i.product.price)} = {rub(s)}")
    lines += ["", f"Итого: <b>{rub(total)}</b>"]
    if total < config.FREE_DELIVERY_FROM:
        lines.append(f"До бесплатной доставки: {rub(config.FREE_DELIVERY_FROM - total)}")
    return "\n".join(lines)


ASK_NAME = "Оформляем заказ 📝\n\nКак к вам обращаться?"
ASK_PHONE = "Телефон для связи — нажмите кнопку ниже или напишите номер."
ASK_DELIVERY = "Как получить заказ?"
ASK_ADDRESS = "Адрес доставки: улица, дом, квартира, подъезд и этаж."
ASK_PAYMENT = "Как удобнее оплатить?"


def checkout_summary(items: list[CartItem], data: dict, delivery_price: int) -> str:
    total = sum(i.product.price * i.qty for i in items)
    lines = ["Проверьте заказ:", ""]
    lines += [f"• {i.product.title} — {i.qty} шт." for i in items]
    where = data.get("address") if data["delivery"] == Delivery.COURIER.value else config.PICKUP_ADDRESS
    lines += [
        "",
        f"👤 {data['name']}, {data['phone']}",
        f"🚚 {DELIVERY[data['delivery']]}: {where}",
        f"💳 {PAYMENT[data['payment']]}",
        "",
        f"Товары: {rub(total)}",
        f"Доставка: {rub(delivery_price) if delivery_price else 'бесплатно'}",
        f"<b>К оплате: {rub(total + delivery_price)}</b>",
    ]
    return "\n".join(lines)


def order_accepted(order: Order) -> str:
    if order.payment == Payment.CARD.value:
        tail = "Осталось оплатить — счёт ниже 👇"
    else:
        tail = "Оплата при получении. Мы напишем, когда заказ поедет."
    return f"Заказ №{order.id} оформлен 🎉\nСумма: <b>{rub(order.total)}</b>\n\n{tail}"


def paid(order: Order) -> str:
    return f"Оплата получена, спасибо! 💳\nЗаказ №{order.id} передан в сборку."


def status_changed(order: Order) -> str:
    return f"Заказ №{order.id}: {STATUS[order.status]}"


def my_orders(orders: list[Order]) -> str:
    if not orders:
        return "Заказов пока нет."
    lines = ["📋 <b>Ваши заказы</b>", ""]
    for o in orders:
        lines.append(f"№{o.id} от {o.created_at:%d.%m} · {rub(o.total)} · {STATUS[o.status]}")
    return "\n".join(lines)


def admin_order(order: Order) -> str:
    lines = [f"<b>Заказ №{order.id}</b> · {STATUS[order.status]}",
             f"{order.created_at:%d.%m.%Y %H:%M}", ""]
    lines += [f"• {i.title} — {i.qty} × {rub(i.price)}" for i in order.items]
    lines += [
        "",
        f"👤 {order.customer_name}, {order.phone}",
        f"🚚 {DELIVERY[order.delivery]}: {order.address}",
        f"💳 {PAYMENT[order.payment]}",
        f"Сумма: <b>{rub(order.total)}</b>"
        + (f" (доставка {rub(order.delivery_price)})" if order.delivery_price else ""),
    ]
    return "\n".join(lines)


def admin_dashboard(stats: dict) -> str:
    return ("🛠 <b>Админка</b>\n\n"
            f"Сегодня заказов: {stats['orders']}\n"
            f"Выручка за сегодня: {rub(stats['revenue'])}\n"
            f"Ждут обработки: {stats['waiting']}")
