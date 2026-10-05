"""Сторона покупателя: каталог, корзина, оформление заказа, оплата."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery, ReplyKeyboardRemove

from . import config, keyboards as kb, services, texts
from .db import session_scope
from .keyboards import CartChange, Cat, Choice, Nav, Prod
from .models import Delivery, Payment
from .notify import notify_admins

router = Router(name="user")


class CheckoutForm(StatesGroup):
    name = State()
    phone = State()
    delivery = State()
    address = State()
    payment = State()
    confirm = State()


async def show(cb: CallbackQuery, text: str, markup) -> None:
    """Перерисовать сообщение под кнопкой. «Ничего не изменилось» — не ошибка."""
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            raise
    await cb.answer()


# ---------- меню и каталог ----------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.welcome(message.from_user.first_name), reply_markup=kb.main_menu())


@router.callback_query(Nav.filter(F.to == "menu"))
async def menu(cb: CallbackQuery) -> None:
    await show(cb, texts.welcome(cb.from_user.first_name), kb.main_menu())


@router.callback_query(Nav.filter(F.to == "catalog"))
async def catalog(cb: CallbackQuery) -> None:
    with session_scope() as s:
        markup = kb.categories(services.categories(s))
    await show(cb, "☕ <b>Каталог</b>\nВыберите раздел:", markup)


@router.callback_query(Cat.filter())
async def category(cb: CallbackQuery, callback_data: Cat) -> None:
    with session_scope() as s:
        cat = next((c for c in services.categories(s) if c.id == callback_data.id), None)
        title = f"{cat.emoji} <b>{cat.title}</b>" if cat else "Раздел"
        markup = kb.products(services.products_in(s, callback_data.id))
    await show(cb, title, markup)


@router.callback_query(Prod.filter())
async def product(cb: CallbackQuery, callback_data: Prod) -> None:
    with session_scope() as s:
        try:
            p = services.get_product(s, callback_data.id)
        except services.ShopError as exc:
            await cb.answer(str(exc), show_alert=True)
            return
        qty = services.cart_qty(s, cb.from_user.id, p.id)
        text, markup = texts.product_card(p, qty), kb.product(p, qty)
    await show(cb, text, markup)


# ---------- корзина ----------

@router.callback_query(CartChange.filter())
async def cart_change(cb: CallbackQuery, callback_data: CartChange) -> None:
    with session_scope() as s:
        try:
            qty = services.change_cart(s, cb.from_user.id, callback_data.product_id, callback_data.delta)
        except services.ShopError as exc:
            await cb.answer(str(exc), show_alert=True)
            return
        if callback_data.view == "product":
            p = services.get_product(s, callback_data.product_id)
            text, markup = texts.product_card(p, qty), kb.product(p, qty)
        else:
            items = services.cart_items(s, cb.from_user.id)
            text, markup = texts.cart(items), kb.cart(items)
    await show(cb, text, markup)


@router.callback_query(Nav.filter(F.to == "cart"))
async def cart(cb: CallbackQuery) -> None:
    with session_scope() as s:
        items = services.cart_items(s, cb.from_user.id)
        text, markup = texts.cart(items), kb.cart(items)
    await show(cb, text, markup)


@router.callback_query(Nav.filter(F.to == "orders"))
async def my_orders(cb: CallbackQuery) -> None:
    with session_scope() as s:
        text = texts.my_orders(services.user_orders(s, cb.from_user.id))
    await show(cb, text, kb.main_menu())


# ---------- оформление ----------

@router.callback_query(Choice.filter(F.field == "checkout"))
async def checkout_start(cb: CallbackQuery, state: FSMContext) -> None:
    with session_scope() as s:
        empty = not services.cart_items(s, cb.from_user.id)
    if empty:
        await cb.answer("Корзина пуста", show_alert=True)
        return
    await state.set_state(CheckoutForm.name)
    await cb.message.answer(texts.ASK_NAME)
    await cb.answer()


@router.message(CheckoutForm.name, F.text)
async def checkout_name(message: Message, state: FSMContext) -> None:
    try:
        name = services.clean_name(message.text)
    except services.ShopError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(name=name)
    await state.set_state(CheckoutForm.phone)
    await message.answer(texts.ASK_PHONE, reply_markup=kb.share_phone())


@router.message(CheckoutForm.phone)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else (message.text or "")
    try:
        phone = services.normalize_phone(raw)
    except services.ShopError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(phone=phone)
    await state.set_state(CheckoutForm.delivery)
    await message.answer(f"Номер {phone} ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(texts.ASK_DELIVERY, reply_markup=kb.delivery())


@router.callback_query(CheckoutForm.delivery, Choice.filter(F.field == "delivery"))
async def checkout_delivery(cb: CallbackQuery, callback_data: Choice, state: FSMContext) -> None:
    await state.update_data(delivery=callback_data.value)
    if callback_data.value == Delivery.COURIER.value:
        await state.set_state(CheckoutForm.address)
        await show(cb, texts.ASK_ADDRESS, None)
    else:
        await state.set_state(CheckoutForm.payment)
        await show(cb, texts.ASK_PAYMENT, kb.payment(bool(config.PAYMENT_PROVIDER_TOKEN)))


@router.message(CheckoutForm.address, F.text)
async def checkout_address(message: Message, state: FSMContext) -> None:
    address = " ".join(message.text.split())
    if len(address) < 5:
        await message.answer("Адрес слишком короткий — улица, дом и квартира.")
        return
    await state.update_data(address=address)
    await state.set_state(CheckoutForm.payment)
    await message.answer(texts.ASK_PAYMENT, reply_markup=kb.payment(bool(config.PAYMENT_PROVIDER_TOKEN)))


@router.callback_query(CheckoutForm.payment, Choice.filter(F.field == "payment"))
async def checkout_payment(cb: CallbackQuery, callback_data: Choice, state: FSMContext) -> None:
    await state.update_data(payment=callback_data.value)
    data = await state.get_data()
    with session_scope() as s:
        items = services.cart_items(s, cb.from_user.id)
        price = services.delivery_price(services.cart_total(items), Delivery(data["delivery"]))
        text = texts.checkout_summary(items, data, price)
    await state.set_state(CheckoutForm.confirm)
    await show(cb, text, kb.confirm())


@router.callback_query(CheckoutForm.confirm, Choice.filter(F.field == "confirm"))
async def checkout_confirm(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    checkout = services.Checkout(name=data["name"], phone=data["phone"], delivery=Delivery(data["delivery"]),
                                 address=data.get("address", ""), payment=Payment(data["payment"]))
    with session_scope() as s:
        try:
            order = services.create_order(s, cb.from_user.id, checkout)
        except services.ShopError as exc:
            await cb.answer(str(exc), show_alert=True)
            return
        order_id, items_total, delivery_cost = order.id, order.items_total, order.delivery_price
        accepted, for_admin = texts.order_accepted(order), texts.admin_order(order)
        admin_markup = kb.admin_order(order)
    await state.clear()
    await show(cb, accepted, None)

    if checkout.payment == Payment.CARD:
        prices = [LabeledPrice(label="Товары", amount=items_total)]
        if delivery_cost:
            prices.append(LabeledPrice(label="Доставка", amount=delivery_cost))
        await cb.bot.send_invoice(
            chat_id=cb.from_user.id, title=f"Заказ №{order_id}", description=config.SHOP_NAME,
            payload=f"order:{order_id}", provider_token=config.PAYMENT_PROVIDER_TOKEN,
            currency=config.CURRENCY, prices=prices)
    await notify_admins(cb.bot, "🆕 " + for_admin, admin_markup)


# ---------- оплата ----------

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Последняя проверка перед списанием: Telegram ждёт ответа не дольше 10 секунд."""
    order_id = int(query.invoice_payload.split(":")[1])
    with session_scope() as s:
        ok = services.can_pay(s, order_id, query.from_user.id, query.total_amount)
    if ok:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Заказ уже оплачен или изменился. Оформите его заново.")


@router.message(F.successful_payment)
async def paid(message: Message) -> None:
    sp = message.successful_payment
    order_id = int(sp.invoice_payload.split(":")[1])
    with session_scope() as s:
        order = services.mark_paid(s, order_id, sp.telegram_payment_charge_id)
        text, for_admin, admin_markup = texts.paid(order), texts.admin_order(order), kb.admin_order(order)
    await message.answer(text, reply_markup=kb.main_menu())
    await notify_admins(message.bot, "💳 " + for_admin, admin_markup)
