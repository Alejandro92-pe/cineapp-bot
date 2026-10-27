import base64
import hashlib
import hmac
import io
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from flask import Blueprint, jsonify, request, g, current_app, Response, send_from_directory
from PIL import Image
from billing.config import PLAN, METHODS, checkout_url
from billing.store import PaymentError
from billing.webhook import process_bmc
from security import owner_access


def payment_routes(store, security_store, legacy_expiry):
    bp = Blueprint("payments", __name__)
    default_qr = Path(__file__).resolve().parents[1]/"static"/"qr-yape.png"

    def qr_asset(method):
        result = store.qr(method)
        if result:
            return result
        if method == "yape_plin" and default_qr.exists():
            return {"data": default_qr.read_bytes(), "mime": "image/png", "recipient": "Richard Quiroz"}

    def enabled(method):
        if method == "bmc":
            return bool(checkout_url()) and (store.local or os.getenv("BMC_MONTHLY_READY") == "true")
        return bool(qr_asset(method))

    def public_order(row):
        allowed = ("id", "code", "method", "amount_minor", "currency", "days", "status", "reference", "payer", "paid_date", "reason", "created_at", "expires_at")
        return {k: row.get(k) for k in allowed}

    @bp.get("/membresia")
    def membership():
        response = send_from_directory("static/payments", "membership.html")
        if store.local and not current_app.config.get('TELEGRAM_PREVIEW'):
            response.direct_passthrough = False
            response.set_data(response.get_data(as_text=True).replace("https://telegram.org/js/telegram-web-app.js", "/static/telegram-local.js"))
        return response

    @bp.get("/api/payments/config")
    def config():
        methods = []
        for key, value in METHODS.items():
            asset = qr_asset(key) if key != "bmc" else None
            methods.append({"id": key, **value, "available": enabled(key),
                "qr": f"/api/payments/qr/{key}" if asset else None, "recipient": asset["recipient"] if asset else None})
        return jsonify(plan=PLAN, methods=methods, local=store.local)

    @bp.get("/api/payments/qr/<method>")
    def qr(method):
        if method not in ("yape_plin", "binance"):
            return jsonify(error="QR no encontrado."), 404
        asset = qr_asset(method)
        if not asset:
            return jsonify(error="QR pendiente de configuración."), 404
        response = Response(asset["data"], mimetype=asset["mime"])
        response.headers["Content-Disposition"] = f'inline; filename="{method}-qr.{"png" if asset["mime"] == "image/png" else "jpg"}"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/api/payments/mine")
    def mine():
        account_id = g.identity["account"]["id"]
        expires = max(store.expiry(account_id), legacy_expiry(account_id))
        permanent = owner_access(g.identity['account'])
        return jsonify(orders=[public_order(r) for r in store.history(account_id)], active=permanent or expires>time.time(),
            permanent=permanent, access_source='owner' if permanent else 'membership',
            expires_at=datetime.fromtimestamp(expires, timezone.utc).isoformat() if expires and not permanent else None)

    @bp.post("/api/payments/orders")
    def create():
        if owner_access(g.identity['account']):
            return jsonify(error='Tu cuenta de propietario tiene acceso permanente. No necesitas comprar una membresía.',code='owner_access'), 409
        method = request.json.get("method")
        if not isinstance(method, str) or method not in METHODS:
            return jsonify(error="Método inválido."), 400
        if not enabled(method):
            return jsonify(error="Este método todavía no está disponible. Elige otra opción."), 409
        account_id = g.identity["account"]["id"]
        if not security_store.allow_attempt("checkout:"+account_id, 30):
            return jsonify(error="Demasiados intentos. Espera unos minutos."), 429
        row = store.create(account_id, method)
        return jsonify(order=public_order(row), checkout_url=checkout_url() if method == "bmc" and not store.local else None, local=store.local)

    @bp.post("/api/payments/orders/<order_id>/report")
    def report(order_id):
        row = store.get(order_id)
        if not row or row["account_id"] != g.identity["account"]["id"]:
            return jsonify(error="Solicitud no encontrada."), 404
        body = request.json
        reference = re.sub(r"[\s-]", "", str(body.get("reference", ""))).upper()
        payer = str(body.get("payer", "")).strip()
        paid_date = str(body.get("paid_date", ""))
        if not re.fullmatch(r"[A-Z0-9]{5,100}", reference) or not 2 <= len(payer) <= 80:
            return jsonify(error="Revisa el número de operación y el nombre del titular que pagó."), 400
        try:
            date.fromisoformat(paid_date)
            result = store.report(order_id, g.identity["account"]["id"], reference, payer, paid_date)
        except (ValueError, PaymentError) as error:
            return jsonify(error=str(error) if isinstance(error, PaymentError) else "Revisa la fecha del pago."), 400
        return jsonify(order=public_order(result))

    @bp.get("/api/admin/payments")
    def admin_list():
        return jsonify(orders=[{**public_order(row), "name": row["name"], "email": row["email"]} for row in store.history()], reviews=store.reviews(), local=store.local)

    @bp.post("/api/admin/payments/<order_id>/decide")
    def decide(order_id):
        body = request.json
        if body.get("decision") not in ("approve", "reject"):
            return jsonify(error="Decisión inválida."), 400
        approved = body["decision"] == "approve"
        reason = str(body.get("reason", "")).strip()
        if approved and body.get("confirmed") is not True:
            return jsonify(error="Comprueba el ingreso en tu billetera antes de aprobar."), 400
        if not approved and not 5 <= len(reason) <= 300:
            return jsonify(error="Explica al usuario por qué no se pudo confirmar su pago."), 400
        row = store.get(order_id)
        if not row:
            return jsonify(error="Solicitud no encontrada."), 404
        try:
            result = store.decide(order_id, approved, reviewer=g.identity["account"]["id"],
                baseline=legacy_expiry(row["account_id"]), reason=reason)
            return jsonify(order=public_order(result))
        except PaymentError as error:
            return jsonify(error=str(error)), 409

    @bp.post("/api/admin/payments/qr")
    def upload_qr():
        body = request.json
        method, recipient = body.get("method"), str(body.get("recipient", "")).strip()
        if method not in ("yape_plin", "binance") or not 2 <= len(recipient) <= 100 or body.get("confirmed") is not True:
            return jsonify(error="Selecciona el método, indica el receptor y confirma que el QR es tuyo."), 400
        try:
            data = base64.b64decode(body.get("data", ""), validate=True)
            if not 100 <= len(data) <= 1024*1024:
                raise ValueError()
            with Image.open(io.BytesIO(data)) as picture:
                if picture.format not in ("PNG", "JPEG") or not (128 <= picture.width <= 2500 and 128 <= picture.height <= 2500):
                    raise ValueError()
                mime = "image/png" if picture.format == "PNG" else "image/jpeg"
                picture.verify()
        except Exception:
            return jsonify(error="Usa el QR oficial en PNG o JPG, entre 128 y 2500 px y hasta 1 MB."), 400
        store.save_qr(method, data, mime, recipient)
        return jsonify(success=True)

    @bp.post("/api/admin/payments/<order_id>/simulate")
    def simulate(order_id):
        if not store.local or not current_app.config["SECURITY_LOCAL"]:
            return jsonify(error="No disponible."), 404
        row = store.get(order_id)
        if not row or row["method"] != "bmc":
            return jsonify(error="Solicitud BMC no encontrada."), 404
        from billing.config import product_id
        payload = {"type": "extra_purchase.created", "live_mode": True, "created": int(time.time()), "data": {
            "id": int(hashlib.sha256(order_id.encode()).hexdigest()[:12],16), "status": "succeeded", "refunded": "false",
            "amount": 1.50, "currency": "USD", "extras": [{"id": int(product_id()), "quantity": 1, "question_answers": [row["code"]]}]}}
        raw = json.dumps(payload).encode()
        signature = hmac.new(os.environ["BMC_WEBHOOK_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
        result, status = process_bmc(raw, signature, store, legacy_expiry)
        return jsonify(**result, simulated=True), status

    return bp
