import pytest
from sqlalchemy import select

from app import config, services
from app.models import Delivery, OrderStatus, Payment, Product
from app.services import Checkout, ShopError

USER = 1001


def product(s, title_start):
    return s.scalar(select(Product).where(Product.title.startswith(title_start)))


def order_for(s, delivery=Delivery.COURIER, payment=Payment.CASH):
    return services.create_order(s, USER, Checkout("Анна", "+79991234567", delivery, "ул. Ленина, 1, кв. 5", payment))


# ---------- корзина ----------

def test_add_and_remove_from_cart(s):
    p = product(s, "Колумбия")
    assert services.change_cart(s, USER, p.id, 1) == 1
    assert services.change_cart(s, USER, p.id, 1) == 2
    assert services.change_cart(s, USER, p.id, -1) == 1
    assert services.change_cart(s, USER, p.id, -1) == 0
    assert services.cart_items(s, USER) == []


def test_cannot_put_more_than_stock(s):
    p = product(s, "Ручная кофемолка")          # на складе 4
    services.change_cart(s, USER, p.id, 4)
    with pytest.raises(ShopError, match="только 4"):
        services.change_cart(s, USER, p.id, 1)


def test_out_of_stock_product_cannot_be_added(s):
    with pytest.raises(ShopError, match="только 0"):
        services.change_cart(s, USER, product(s, "Кения").id, 1)


def test_carts_are_separate_per_user(s):
    p = product(s, "Колумбия")
    services.change_cart(s, USER, p.id, 2)
    services.change_cart(s, 2002, p.id, 1)
    assert services.cart_qty(s, USER, p.id) == 2
    assert services.cart_qty(s, 2002, p.id) == 1


# ---------- доставка ----------

@pytest.mark.parametrize(
    "items_total, delivery, price",
    [(100000, Delivery.COURIER, config.DELIVERY_PRICE),
     (config.FREE_DELIVERY_FROM, Delivery.COURIER, 0),
     (100000, Delivery.PICKUP, 0)],
    ids=["courier-paid", "courier-free-from-threshold", "pickup-free"],
)
def test_delivery_price(items_total, delivery, price):
    assert services.delivery_price(items_total, delivery) == price


# ---------- заказ ----------

def test_order_fixes_prices_takes_stock_and_clears_cart(s):
    p = product(s, "Эфиопия Иргачеффе")       # 890 ₽, на складе 24
    services.change_cart(s, USER, p.id, 2)
    order = order_for(s)
    assert order.items_total == 178000
    assert order.delivery_price == config.DELIVERY_PRICE   # меньше порога бесплатной доставки
    assert order.total == 178000 + config.DELIVERY_PRICE
    assert [(i.title, i.price, i.qty) for i in order.items] == [(p.title, 89000, 2)]
    assert p.stock == 22
    assert services.cart_items(s, USER) == []

    p.price = 99900                            # цену потом подняли — в заказе осталась старая
    s.flush()
    assert order.items[0].price == 89000


def test_order_fails_if_stock_ran_out_meanwhile(s):
    p = product(s, "Ручная кофемолка")
    services.change_cart(s, USER, p.id, 3)
    p.stock = 1                                # пока покупатель думал, раскупили
    with pytest.raises(ShopError, match="на складе 1"):
        order_for(s)


def test_empty_cart_and_missing_address_are_rejected(s):
    with pytest.raises(ShopError, match="пуста"):
        order_for(s)
    services.change_cart(s, USER, product(s, "Колумбия").id, 1)
    with pytest.raises(ShopError, match="адрес"):
        services.create_order(s, USER, Checkout("Анна", "+79991234567", Delivery.COURIER, "", Payment.CASH))


def test_pickup_uses_shop_address(s):
    services.change_cart(s, USER, product(s, "Колумбия").id, 1)
    order = order_for(s, delivery=Delivery.PICKUP)
    assert order.address == config.PICKUP_ADDRESS
    assert order.delivery_price == 0


# ---------- статусы и оплата ----------

def test_status_flow_and_forbidden_jump(s):
    services.change_cart(s, USER, product(s, "Колумбия").id, 1)
    order = order_for(s)
    with pytest.raises(ShopError, match="Нельзя"):
        services.set_status(s, order.id, OrderStatus.DONE)
    for status in (OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DONE):
        services.set_status(s, order.id, status)
    assert order.status == "done"


def test_cancel_returns_goods_to_stock(s):
    p = product(s, "Бразилия")                 # 12 шт.
    services.change_cart(s, USER, p.id, 5)
    order = order_for(s)
    assert p.stock == 7
    services.set_status(s, order.id, OrderStatus.CANCELLED)
    assert p.stock == 12


def test_payment_checks(s):
    services.change_cart(s, USER, product(s, "Колумбия").id, 1)
    order = order_for(s, payment=Payment.CARD)
    assert services.can_pay(s, order.id, USER, order.total)
    assert not services.can_pay(s, order.id, USER, order.total - 1)    # сумма не совпала
    assert not services.can_pay(s, order.id, 999, order.total)         # чужой заказ
    services.mark_paid(s, order.id, "charge-1")
    assert order.status == "paid" and order.paid_at and order.charge_id == "charge-1"
    assert not services.can_pay(s, order.id, USER, order.total)        # повторно не списываем


# ---------- контакты ----------

@pytest.mark.parametrize(
    "raw, phone",
    [("+7 999 123-45-67", "+79991234567"), ("8 (999) 123 45 67", "+79991234567"), ("9991234567", "+79991234567")],
    ids=["plus7", "eight", "ten-digits"],
)
def test_phone_is_normalized(raw, phone):
    assert services.normalize_phone(raw) == phone


@pytest.mark.parametrize("raw", ["12345", "телефон", "+1 202 555 0100"], ids=["short", "text", "foreign"])
def test_bad_phone_is_rejected(raw):
    with pytest.raises(ShopError):
        services.normalize_phone(raw)


def test_name_is_cleaned():
    assert services.clean_name("  Анна   Петрова ") == "Анна Петрова"
    with pytest.raises(ShopError):
        services.clean_name("А")
