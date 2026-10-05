from app import keyboards as kb
from app.main import build_dispatcher


def test_dispatcher_builds_with_both_routers():
    dp = build_dispatcher()
    assert [r.name for r in dp.sub_routers] == ["admin", "user"]


def test_callback_data_fits_telegram_limit():
    """Telegram принимает в callback_data не больше 64 байт."""
    samples = [
        kb.CartChange(product_id=999999, delta=-1, view="product"),
        kb.Choice(field="checkout", value="start"),
        kb.Choice(field="delivery", value="courier"),
        kb.AdminStatus(id=999999, status="cancelled"),
        kb.AdminNav(to="dashboard"),
    ]
    for data in samples:
        assert len(data.pack().encode()) <= 64, data.pack()
