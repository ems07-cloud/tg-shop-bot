import logging

from . import config

log = logging.getLogger(__name__)


async def notify_admins(bot, text: str, markup=None) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as exc:  # админ не запускал бота и т. п. — заказ от этого не страдает
            log.warning("не удалось уведомить админа %s: %s", admin_id, exc)
