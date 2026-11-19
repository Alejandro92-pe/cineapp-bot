"""Signed Buy Me a Coffee webhooks.

- membership.*: the IMAX monthly membership. Linked to an account by email (account email or the email
  the person gave on the membership page). Access lasts until the paid period ends.
- extra_purchase.*: the old one-off shop product, still accepted while it is published. It is linked by
  the private QH- code the buyer pastes in the product question.

Every delivery is written to bmc_events with what the web did, so the admin can see why.
"""
import hashlib
import hmac
import json
import os
import re
import math
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from billing.config import product_id, membership_level_id, MEMBERSHIP_PRICE, LEGACY_SHOP_PRICE, PRICE_TOLERANCE
from billing.store import PaymentError

PERU = timezone(timedelta(hours=-5))


def _day(ts):
    return datetime.fromtimestamp(ts, PERU).strftime("%d/%m/%Y")


def _price_ok(value, price):
    try:
        amount = Decimal(str(value))
        return amount.is_finite() and abs(amount - Decimal(price)) <= Decimal(PRICE_TOLERANCE)
    except InvalidOperation:
        return False


def _true(value):
    return value is True or str(value).lower() == "true"


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
    data, kind = payload["data"], str(payload.get("type", ""))
    event_id = payload.get("event_id") or hashlib.sha256(raw).hexdigest()[:32]
    context = dict(object_id=data.get("id"), email=(data.get("supporter_email") or "").strip().lower() or None,
                   name=data.get("supporter_name"), amount=data.get("amount"), currency=data.get("currency"))

    def done(result, status, outcome, detail, account_id=None):
        try:
            store.log_event(event_id, kind, outcome, detail, account_id=account_id, payload=payload, **context)
        except Exception:  # logging must never make BMC retry a valid payment
            pass
        return result, status

    if payload.get("live_mode") is False:
        return done({"received": True, "test_event": True}, 200, "prueba", "Evento de prueba enviado desde BMC: no cambia nada.")
    if payload.get("live_mode") is not True:
        return done({"error": "Falta live_mode."}, 400, "rechazado", "El aviso no indica si es real o de prueba.")
    payment_id = data.get("id")
    if type(payment_id) is not int or payment_id <= 0:
        return done({"error": "Falta el identificador del pago."}, 400, "rechazado", "El aviso no trae el número de pago.")
    if kind.startswith("membership."):
        return _membership(kind, data, store, legacy_expiry, done)
    if kind in ("extra_purchase.created", "extra_purchase.updated"):
        return _shop(kind, payload, data, store, legacy_expiry, done)
    if kind == "extra_purchase.refunded":
        store.review(payment_id, "Reembolso de la tienda: revisa si corresponde retirar el acceso.")
        return done({"received": True, "activated": False}, 200, "revisar", "Reembolso de una compra de la tienda. El acceso no se retira solo.")
    return done({"received": True, "activated": False}, 200, "ignorado", f"Tipo de aviso que la web no usa ({kind}).")


def _membership(kind, data, store, legacy_expiry, done):
    membership_id = data["id"]
    email = (data.get("supporter_email") or "").strip().lower()
    period_end = data.get("current_period_end")
    if type(period_end) not in (int, float) or not math.isfinite(period_end):
        period_end = None
    canceled = _true(data.get("canceled")) or kind == "membership.cancelled"
    row = store.save_membership(membership_id, email=email or None, name=data.get("supporter_name"),
        level_id=str(data.get("membership_level_id")), level_name=data.get("membership_level_name"),
        status=str(data.get("status") or "desconocido")[:20], amount=str(data.get("amount")), currency=data.get("currency"),
        period_end=period_end, canceled=1 if canceled else 0)
    account_id = row.get("account_id")
    ok = {"received": True, "activated": False}
    if str(data.get("membership_level_id")) != membership_level_id():
        return done(ok, 200, "revisar", f"Membresía de otro nivel ({data.get('membership_level_name')}), no IMAX: no se activa.", account_id)
    if canceled or data.get("status") != "active" or _true(data.get("paused")):
        until = f" Sigue con acceso hasta el {_day(period_end)}." if period_end else ""
        return done(ok, 200, "cancelada", "Membresía cancelada o pausada en BMC: no se renueva." + until, account_id)
    if data.get("currency") != "USD" or not _price_ok(data.get("amount"), MEMBERSHIP_PRICE):
        return done(ok, 200, "revisar", f"Importe {data.get('amount')} {data.get('currency')}: se esperaba US${MEMBERSHIP_PRICE}.", account_id)
    if period_end is None or period_end < time.time() - 86400 or period_end > time.time() + 40 * 86400:
        return done(ok, 200, "revisar", "La fecha de fin del mes pagado no es válida.", account_id)
    how = None
    if not account_id:
        account_id, how = store.match_account(email)
        if not account_id:
            return done(ok, 200, "sin_vincular", how + " Vincúlala desde el admin para activar el acceso.")
    try:
        expires = store.grant_membership(membership_id, account_id, period_end, baseline=legacy_expiry(account_id),
                                         link_method="email" if how else None)
    except PaymentError as error:
        return done(ok, 200, "revisar", str(error), account_id)
    note = f" Vinculada por {how}." if how else ""
    return done({"success": True, "activated": True}, 200, "activado", f"Acceso hasta el {_day(expires)}.{note}", account_id)


def _shop(kind, payload, data, store, legacy_expiry, done):
    payment_id = data["id"]
    extras = data.get("extras")
    if not isinstance(extras, list) or len(extras) != 1 or not isinstance(extras[0], dict):
        return done({"error": "Debe comprarse una unidad del producto mensual."}, 422, "rechazado", "La compra no trae un único producto.")
    extra = extras[0]
    valid_amount = _price_ok(extra.get("amount"), LEGACY_SHOP_PRICE) and _price_ok(data.get("amount"), LEGACY_SHOP_PRICE)
    if (str(extra.get("id")) != product_id() or type(extra.get("quantity")) is not int or extra["quantity"] != 1
            or not valid_amount or data.get("currency") != "USD" or extra.get("currency") != "USD"):
        store.review(payment_id, "El producto, importe, moneda o cantidad no corresponde al acceso mensual de US$1.50.")
        return done({"received": True, "review": True, "activated": False}, 200, "revisar",
                    f"Producto «{extra.get('title')}» por {data.get('amount')} {data.get('currency')}: no es el acceso de la tienda.")
    if data.get("status") != "succeeded" or not (data.get("refunded") is False or data.get("refunded") == "false"):
        store.review(payment_id, "El pago no está confirmado o figura reembolsado.")
        return done({"received": True, "review": True, "activated": False}, 200, "revisar", "El pago no figura como cobrado o fue reembolsado.")
    # Use documented shop question_answers. Never infer identity from an unverified email.
    answers = extra.get("question_answers", [])
    codes = {answer.strip().upper() for answer in answers if isinstance(answer, str) and re.fullmatch(r"QH-[A-Fa-f0-9]{20}", answer.strip())} if isinstance(answers, list) else set()
    if len(codes) != 1:
        if kind == "extra_purchase.created" and not answers:
            # BMC sends the buyer's answer a few seconds later, in extra_purchase.updated.
            return done({"received": True, "review": True, "activated": False}, 200, "esperando",
                        "BMC aún no envía el código de compra; llega en el aviso «Extra updated».")
        store.review(payment_id, "Falta un código de compra único en la respuesta del producto. Revisar en Buy Me a Coffee.")
        written = ", ".join(str(a)[:40] for a in answers) if isinstance(answers, list) and answers else "nada"
        return done({"received": True, "review": True, "activated": False}, 200, "revisar",
                    f"El comprador no escribió un código QH- válido (escribió: {written}).")
    code = next(iter(codes))
    order = store.by_code(code)
    if not order or order["method"] != "bmc":
        store.review(payment_id, "Código de compra desconocido o de otro método.")
        return done({"received": True, "review": True, "activated": False}, 200, "revisar", f"El código {code} no existe en la web.")
    created = data.get("created_at", payload.get("created"))
    if type(created) not in (int, float) or not math.isfinite(created) or created < order["created_at"]-300 or created > time.time()+300:
        store.review(payment_id, "El pago es anterior a la solicitud de acceso.")
        return done({"received": True, "review": True, "activated": False}, 200, "revisar",
                    "El pago es anterior al código de compra.", order["account_id"])
    try:
        result = store.decide(order["id"], True, baseline=legacy_expiry(order["account_id"]), provider_reference=str(payment_id))
        dup = result.get("duplicate", False)
        return done({"success": True, "duplicate": dup}, 200, "duplicado" if dup else "activado",
                    "Este pago ya había activado el acceso." if dup else f"Acceso hasta el {_day(result['expires_at'])} (tienda).",
                    order["account_id"])
    except PaymentError as error:
        store.review(payment_id, str(error))
        return done({"received": True, "review": True, "activated": False}, 200, "revisar", str(error), order["account_id"])
