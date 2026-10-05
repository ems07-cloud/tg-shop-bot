import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./shop.db")

# Telegram Payments: токен провайдера из @BotFather (ЮKassa, Сбер и т. д.).
# Пусто — оплата картой в боте выключена, остаётся оплата при получении.
PAYMENT_PROVIDER_TOKEN: str = os.getenv("PAYMENT_PROVIDER_TOKEN", "")
CURRENCY: str = os.getenv("CURRENCY", "RUB")

# Кто видит /admin и получает уведомления о заказах: id через запятую
ADMIN_IDS: set[int] = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}

SHOP_NAME: str = os.getenv("SHOP_NAME", "Обжарка «Зерно»")

# Доставка: курьером платно, от порога — бесплатно; самовывоз всегда бесплатно. В копейках.
DELIVERY_PRICE: int = int(os.getenv("DELIVERY_PRICE", "30000"))
FREE_DELIVERY_FROM: int = int(os.getenv("FREE_DELIVERY_FROM", "300000"))
PICKUP_ADDRESS: str = os.getenv("PICKUP_ADDRESS", "Москва, ул. Примерная, 1 (ежедневно 10:00–21:00)")
