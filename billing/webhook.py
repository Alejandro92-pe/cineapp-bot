"""Signed BMC shop purchases, explicitly matched to a private order code."""
import hashlib
import hmac
import json
import os
import re
import math
import time
from decimal import Decimal, InvalidOperation
from billing.config import product_id
from billing.store import PaymentError


def process_bmc(raw, signature, store, legacy_expiry):
    secret = os.getenv("BMC_WEBHOOK_SECRET", "")
    if len(secret) < 16:
        return {"error": "Webhook pendiente de configuración."}, 503
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return {"error": "Firma inválida."}, 401
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"error": "Evento inválido."}, 400
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        return {"error": "Evento inválido."}, 400
    if payload.get("live_mode") is False:
        return {"received": True, "test_event": True}, 200
    if payload.get("live_mode") is not True:
        return {"error": "Falta live_mode."}, 400
    data = payload["data"]
    payment_id = data.get("id")
    if type(payment_id) is not int or payment_id <= 0:
        return {"error": "Falta el identificador del pago."}, 400
    # Shop answers can arrive after checkout, in extra_purchase.updated.
    # Both events must pass every payment/order check and share the same receipt.
    if payload.get("type") not in ("extra_purchase.created", "extra_purchase.updated"):
        if payload.get("type") == "extra_purchase.refunded" or str(payload.get("type", "")).startswith(("membership.", "recurring_donation.")):
            store.review(payment_id, "Reembolso, actualización o suscripción antigua: requiere conciliación; no se concede otro período.")
        return {"received": True, "activated": False}, 200
    extras = data.get("extras")
    if not isinstance(extras, list) or len(extras) != 1 or not isinstance(extras[0], dict):
        return {"error": "Debe comprarse una unidad del producto mensual."}, 422
    extra = extras[0]
    try:
        amount = Decimal(str(data.get("amount")))
        price = Decimal(str(extra.get("amount")))
        # Real BMC deliveries can differ slightly from the shop price (e.g.
        # 2.97 USD for a 3.00 USD item). Keep the item fixed at 1.50 USD,
        # with at most 2% settlement variance; larger discrepancies need review.
        valid_amount = (amount.is_finite() and price.is_finite()
                        and price == Decimal("1.50")
                        and abs(amount-price) <= Decimal("0.03"))
    except InvalidOperation:
        valid_amount = False
    if (str(extra.get("id")) != product_id() or type(extra.get("quantity")) is not int or extra["quantity"] != 1
            or not valid_amount or data.get("currency") != "USD" or extra.get("currency") != "USD"):
        store.review(payment_id, "El producto, importe, moneda o cantidad no corresponde al acceso mensual de US$1.50.")
        return {"received": True, "review": True, "activated": False}, 200
    if data.get("status") != "succeeded" or not (data.get("refunded") is False or data.get("refunded") == "false"):
        store.review(payment_id, "El pago no está confirmado o figura reembolsado.")
        return {"received": True, "review": True, "activated": False}, 200
    # Use documented shop question_answers. Never infer identity from an unverified email.
    answers = extra.get("question_answers", [])
    codes = {answer.strip().upper() for answer in answers if isinstance(answer, str) and re.fullmatch(r"QH-[A-Fa-f0-9]{20}", answer.strip())} if isinstance(answers, list) else set()
    if len(codes) != 1:
        store.review(payment_id, "Falta un código de compra único en la respuesta del producto. Revisar en Buy Me a Coffee.")
        return {"received": True, "review": True, "activated": False}, 200
    order = store.by_code(next(iter(codes)))
    if not order or order["method"] != "bmc":
        store.review(payment_id, "Código de compra desconocido o de otro método.")
        return {"received": True, "review": True, "activated": False}, 200
    created = data.get("created_at", payload.get("created"))
    if type(created) not in (int, float) or not math.isfinite(created) or created < order["created_at"]-300 or created > time.time()+300:
        store.review(payment_id, "El pago es anterior a la solicitud de acceso.")
        return {"received": True, "review": True, "activated": False}, 200
    try:
        result = store.decide(order["id"], True, baseline=legacy_expiry(order["account_id"]), provider_reference=str(payment_id))
        return {"success": True, "duplicate": result.get("duplicate", False)}, 200
    except PaymentError as error:
        store.review(payment_id, str(error))
        return {"received": True, "review": True, "activated": False}, 200
