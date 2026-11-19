import os

# BMC is now a monthly membership (IMAX, US$2). Yape/Plin and Binance stay as one-off 30-day payments.
PLAN = {"id": "mensual", "nombre": "Acceso mensual", "duracion_dias": 30,
        "precio_dolares": 2.00, "precio_soles": 7.50, "renovacion_automatica": False,
        "pedidos_por_mes": 0}
METHODS = {
    "bmc": {"label": "Buy Me a Coffee", "amount_minor": 200, "currency": "USD", "automatic": True, "recurring": True},
    "yape_plin": {"label": "Yape / Plin", "amount_minor": 750, "currency": "PEN", "automatic": False},
    "binance": {"label": "Binance Pay", "amount_minor": 200, "currency": "USDT", "automatic": False},
}
MEMBERSHIP_PRICE = "2.00"      # IMAX level, per month
LEGACY_SHOP_PRICE = "1.50"     # old shop product, still accepted during the transition
PRICE_TOLERANCE = "0.03"       # BMC settles a few cents below the list price
MEMBERSHIP_GRACE = 36 * 3600   # renewal webhooks can arrive a little after the period ends


def product_id():
    """Old one-off shop product (Embajador). Kept so existing purchase codes still activate."""
    return os.getenv("BMC_MONTHLY_PRODUCT_ID", "517243")


def membership_level_id():
    return os.getenv("BMC_MEMBERSHIP_LEVEL_ID", "283557")


def checkout_url():
    # Fixed merchant page; never use a client-controlled return URL.
    return os.getenv("BMC_MEMBERSHIP_URL", "https://buymeacoffee.com/quehay/membership")
