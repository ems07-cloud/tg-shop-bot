import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from . import config, handlers_admin, handlers_user
from .seed import seed


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_admin.router)   # админ раньше — его команды не перехватит пользовательский роутер
    dp.include_router(handlers_user.router)
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан BOT_TOKEN — скопируйте .env.example в .env и впишите токен")
    seed()                                     # пустую базу заполняет демо-каталогом
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await build_dispatcher().start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
