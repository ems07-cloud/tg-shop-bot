"""Сторона магазина: сводка, заказы в работе, смена статусов, выгрузка в Excel."""
from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from . import config, keyboards as kb, services, texts
from .db import session_scope
from .export import orders_xlsx
from .handlers_user import show
from .keyboards import AdminNav, AdminOrder, AdminStatus
from .models import OrderStatus

router = Router(name="admin")
# всё в этом роутере — только для администраторов магазина
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

IN_WORK = [OrderStatus.NEW, OrderStatus.PAID, OrderStatus.CONFIRMED, OrderStatus.SHIPPED]


@router.message(Command("admin"))
async def admin(message: Message) -> None:
    with session_scope() as s:
        text = texts.admin_dashboard(services.stats_today(s))
    await message.answer(text, reply_markup=kb.admin_dashboard())


@router.callback_query(AdminNav.filter(F.to == "dashboard"))
async def dashboard(cb: CallbackQuery) -> None:
    with session_scope() as s:
        text = texts.admin_dashboard(services.stats_today(s))
    await show(cb, text, kb.admin_dashboard())


@router.callback_query(AdminNav.filter(F.to == "waiting"))
async def waiting(cb: CallbackQuery) -> None:
    with session_scope() as s:
        orders = services.orders_by_status(s, IN_WORK)
        text = f"📥 <b>Заказы в работе: {len(orders)}</b>" if orders else "Заказов в работе нет 🎉"
        markup = kb.admin_orders(orders)
    await show(cb, text, markup)


@router.callback_query(AdminOrder.filter())
async def order_card(cb: CallbackQuery, callback_data: AdminOrder) -> None:
    with session_scope() as s:
        order = s.get(services.Order, callback_data.id)
        if order is None:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        text, markup = texts.admin_order(order), kb.admin_order(order)
    await show(cb, text, markup)


@router.callback_query(AdminStatus.filter())
async def change_status(cb: CallbackQuery, callback_data: AdminStatus) -> None:
    with session_scope() as s:
        try:
            order = services.set_status(s, callback_data.id, OrderStatus(callback_data.status))
        except services.ShopError as exc:
            await cb.answer(str(exc), show_alert=True)
            return
        text, markup = texts.admin_order(order), kb.admin_order(order)
        customer, for_customer = order.user_id, texts.status_changed(order)
    await show(cb, text, markup)
    try:
        await cb.bot.send_message(customer, for_customer)
    except Exception:
        pass  # покупатель мог заблокировать бота — статус всё равно сменился


@router.callback_query(AdminNav.filter(F.to == "export"))
async def export(cb: CallbackQuery) -> None:
    with session_scope() as s:
        orders = services.all_orders(s)
        data = orders_xlsx(orders)
    name = f"orders_{datetime.now():%Y-%m-%d}.xlsx"
    await cb.message.answer_document(BufferedInputFile(data, filename=name),
                                     caption=f"Заказов в файле: {len(orders)}")
    await cb.answer()
