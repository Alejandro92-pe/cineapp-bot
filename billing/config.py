import os

PLAN = {"id": "mensual", "nombre": "Acceso mensual", "duracion_dias": 30,
        "precio_dolares": 1.50, "precio_soles": 5.50, "renovacion_automatica": False,
        "pedidos_por_mes": 0}
METHODS = {
    "bmc": {"label": "Buy Me a Coffee", "amount_minor": 150, "currency": "USD", "automatic": True},
    "yape_plin": {"label": "Yape / Plin", "amount_minor": 550, "currency": "PEN", "automatic": False},
    "binance": {"label": "Binance Pay", "amount_minor": 150, "currency": "USDT", "automatic": False},
}


def product_id():
    return os.getenv("BMC_MONTHLY_PRODUCT_ID", "517243")


def checkout_url():
    # Fixed merchant and product; never use a client-controlled return URL.
    value = product_id()
    if not value.isdigit():
        return None
    return "https://buymeacoffee.com/quehay/e/" + value
