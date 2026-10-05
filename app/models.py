"""Модели магазина. Все деньги — в копейках (int), чтобы не ловить ошибки округления."""
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(str, Enum):
    NEW = "new"              # оформлен, ждёт оплаты или подтверждения
    PAID = "paid"            # оплачен картой в боте
    CONFIRMED = "confirmed"  # подтверждён магазином, собирается
    SHIPPED = "shipped"      # передан курьеру / готов к выдаче
    DONE = "done"            # получен
    CANCELLED = "cancelled"


class Delivery(str, Enum):
    COURIER = "courier"
    PICKUP = "pickup"


class Payment(str, Enum):
    CARD = "card"            # Telegram Payments
    CASH = "cash"            # при получении


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str] = mapped_column(String(8), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)          # копейки
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category] = relationship(back_populates="products")


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    delivery: Mapped[str] = mapped_column(String(10))
    address: Mapped[str] = mapped_column(String(300), default="")
    payment: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(15), default=OrderStatus.NEW.value)
    items_total: Mapped[int] = mapped_column(Integer)    # копейки, без доставки
    delivery_price: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    charge_id: Mapped[str] = mapped_column(String(100), default="")

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def total(self) -> int:
        return self.items_total + self.delivery_price


class OrderItem(Base):
    """Позиция заказа хранит название и цену на момент покупки: товар потом могут изменить."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    title: Mapped[str] = mapped_column(String(150))
    price: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
