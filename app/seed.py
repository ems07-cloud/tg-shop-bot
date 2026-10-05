"""Демо-каталог: магазин свежей обжарки кофе. Запуск: python -m app.seed"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Category, Product

CATALOG = {
    ("Зерновой кофе", "☕", 1): [
        ("Эфиопия Иргачеффе, 250 г", "Яркая кислотность, ноты бергамота и жасмина. Обжарка под фильтр.", 89000, 24),
        ("Колумбия Супремо, 250 г", "Сбалансированный, шоколад и орех. Подходит для эспрессо и турки.", 72000, 40),
        ("Бразилия Сантос, 1 кг", "Плотный и сладкий, карамель и какао. Основа для молочных напитков.", 189000, 12),
        ("Кения АА, 250 г", "Чёрная смородина и томатная сладость, сочное тело.", 99000, 0),
    ],
    ("Дрип-пакеты", "🫖", 2): [
        ("Дрип-пакеты ассорти, 10 шт.", "Пять сортов по два пакета — чтобы выбрать любимый.", 69000, 30),
        ("Дрип-пакеты Эфиопия, 10 шт.", "Фильтр-кофе без оборудования: залил водой — готово.", 75000, 18),
    ],
    ("Для заваривания", "⚙️", 3): [
        ("Воронка V60 керамическая", "Классика для фильтр-кофе, размер 02.", 210000, 6),
        ("Фильтры для V60, 100 шт.", "Бумажные фильтры без привкуса, размер 02.", 45000, 50),
        ("Ручная кофемолка", "Керамические жернова, 25 ступеней помола.", 349000, 4),
    ],
}


def seed_catalog(session: Session) -> bool:
    """Заполняет пустую базу демо-товарами. Возвращает True, если что-то добавлено."""
    if session.scalar(select(Category.id).limit(1)):
        return False
    for (title, emoji, sort), items in CATALOG.items():
        cat = Category(title=title, emoji=emoji, sort=sort)
        session.add(cat)
        session.flush()
        for name, desc, price, stock in items:
            session.add(Product(category_id=cat.id, title=name, description=desc, price=price, stock=stock))
    session.flush()
    return True


def seed() -> None:
    from .db import init_db, session_scope

    init_db()
    with session_scope() as s:
        print("демо-каталог создан" if seed_catalog(s) else "каталог уже заполнен")


if __name__ == "__main__":
    seed()
