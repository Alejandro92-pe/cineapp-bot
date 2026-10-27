import json
import os
import time
import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from conftest import send, register, owner_login, tg_login, signed_telegram, ORIGIN
from security import COOKIE, password_ok, telegram_identity
from security_store import accounts, sessions, events, SecurityStore, digest


def test_registration_hash_cookie_and_no_privilege(client,system):
    response=register(client)
    assert response.status_code==200
    assert not response.json["is_admin"]
    cookie=response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    account=system.security_store.account(email="person@example.test")
    assert account["password_hash"].startswith("$2b$")
    assert "password" not in json.dumps(response.json)
    assert account["telegram_id"] is None
    raw_cookie=client.get_cookie(COOKIE, domain="127.0.0.1").value
    with system.security_store.engine.connect() as c:
        assert c.execute(select(sessions.c.token_hash)).scalar_one()==digest(raw_cookie)


def test_login_rotates_and_logout_revokes(client,system):
    registration=register(client)
    old=client.get_cookie(COOKIE, domain="127.0.0.1").value
    result=send(client,"/api/auth/login",{"email":"person@example.test","password":"Local-user-test-2026!"})
    assert result.status_code==200
    assert client.get_cookie(COOKIE, domain="127.0.0.1").value != old
    assert system.security_store.session(old) is None
    token=client.get_cookie(COOKIE, domain="127.0.0.1").value
    assert send(client,"/api/auth/logout",{},result.json["csrf_token"]).status_code==200
    assert system.security_store.session(token) is None
    assert client.get_cookie(COOKIE, domain="127.0.0.1") is None


@pytest.mark.parametrize("password",["short", "a"*73, "á"*37, None, 123])
def test_unsafe_password_rejected(client,password):
    result=send(client,"/api/auth/register",{"email":"p@example.test","name":"P","password":password})
    assert result.status_code==400


def test_client_cannot_assign_admin_or_telegram(client):
    response=send(client,"/api/auth/register",{"name":"Ale","email":"owner@example.test","password":"Good-password-2026!", "telegram_id":5824989040,"is_admin":True,"admin_id":5824989040})
    assert response.status_code==200
    assert response.json["user"]["telegram_id"] is None and response.json["is_admin"] is False
    assert send(client,"/api/admin/usuarios",{"admin_id":5824989040},response.json["csrf_token"]).status_code==403


@pytest.mark.parametrize("path",["/api/admin/usuarios","/api/admin/pagos","/api/admin/importar_tmdb",
    "/api/admin/marketing/enviar_mensaje","/aprobar_pago","/marcar_entregado","/admin_pedidos"])
def test_admin_id_alone_never_authorizes(client,system,path):
    assert send(client,path,{"admin_id":5824989040,"pagoId":1}).status_code==401
    assert not system.bot.calls


@pytest.mark.parametrize("user_id",[7233740331,5913015573])
def test_removed_admin_ids_are_regular_users(client,user_id):
    response=tg_login(client,user_id)
    assert response.status_code==200 and response.json["is_admin"] is False
    assert send(client,"/api/admin/usuarios",{"admin_id":user_id},response.json["csrf_token"]).status_code==403


def test_only_owner_bcrypt_login(client,monkeypatch):
    monkeypatch.setenv("ADMIN_ID","7233740331,5913015573")
    invalid=send(client,"/api/admin/login",{"admin_id":7233740331,"password":"Local-admin-test-2026!"})
    assert invalid.status_code==401
    result=owner_login(client)
    assert result.status_code==200 and result.json["is_admin"]
    assert send(client,"/api/admin/usuarios",{},result.json["csrf_token"]).status_code==200


def test_plaintext_admin_config_fails_closed(client,monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH","not-a-bcrypt-hash")
    assert owner_login(client).status_code==503


def test_csrf_and_cross_origin_blocked(client):
    result=register(client)
    assert send(client,"/api/auth/logout",{}).status_code==403
    assert send(client,"/api/auth/logout",{},result.json["csrf_token"],headers={"Origin":"https://evil.example"}).status_code==403
    assert client.post("/api/auth/login",data='{}',base_url=ORIGIN).status_code==403


def test_forged_expired_future_and_duplicate_telegram(client):
    good=signed_telegram()
    for raw in [good.replace("900000001","900000002"),signed_telegram(age=3600),signed_telegram(age=-300),good+"&auth_date=1","invalid"]:
        assert send(client,"/api/auth/telegram",{"init_data":raw}).status_code==401


def test_cross_user_read_denied(client):
    result=tg_login(client)
    csrf=result.json["csrf_token"]
    assert send(client,"/api/usuario",{"telegram_id":5824989040},csrf).status_code==403
    assert send(client,"/api/usuario",{},csrf).json["usuario"]["telegram_id"]==900000001


def test_email_account_does_not_inherit_membership(client):
    result=register(client,"demo@example.test")
    assert send(client,"/api/usuario",{},result.json["csrf_token"]).status_code==409
    assert send(client,"/api/download/1",method="GET").status_code==403


def test_link_telegram_requires_proof_and_csrf(client):
    result=register(client)
    assert send(client,"/api/auth/telegram",{"init_data":signed_telegram()}).status_code==403
    linked=send(client,"/api/auth/telegram",{"init_data":signed_telegram()},result.json["csrf_token"])
    assert linked.status_code==200 and linked.json["user"]["telegram_id"]==900000001


def test_password_change_revokes_other_sessions(client,system):
    result=register(client)
    old=client.get_cookie(COOKIE, domain="127.0.0.1").value
    other=system.app.test_client()
    second=send(other,"/api/auth/login",{"email":"person@example.test","password":"Local-user-test-2026!"})
    token=other.get_cookie(COOKIE, domain="127.0.0.1").value
    changed=send(client,"/api/auth/password",{"current_password":"Local-user-test-2026!","password":"Another-good-password!"},result.json["csrf_token"])
    assert changed.status_code==200
    assert system.security_store.session(old) is None and system.security_store.session(token) is None
    assert send(other,"/api/auth/me",method="GET").json["authenticated"] is False


def test_session_expiry(client,system):
    register(client)
    with system.security_store.engine.begin() as c:
        c.execute(sessions.update().values(expires_at=time.time()-1))
    assert send(client,"/api/auth/me",method="GET").json["authenticated"] is False
    assert send(client,"/api/download/1",method="GET").status_code==401


def test_tampered_session_is_not_accepted(client):
    register(client)
    client.set_cookie(COOKIE,"forged-token",domain="127.0.0.1")
    assert send(client,"/api/auth/me",method="GET").json["authenticated"] is False


def test_revoked_membership_is_denied_even_with_future_user_date(client,system):
    tg_login(client)
    system.supabase_service.rows["membresias_activas"][0]["estado"]="inactiva"
    assert send(client,"/api/download/1",method="GET").status_code==403


def test_local_checkout_cannot_create_a_real_payment(client,system):
    result=tg_login(client)
    assert send(client,"/crear_pago_tarjeta",{"plan":"copper","email":"demo@example.test"},result.json["csrf_token"]).status_code==409
    assert system.supabase_service.rows["pagos_manuales"]==[]


def test_rate_limit_persists_and_ignores_forwarded_ip(client):
    for i in range(10):
        assert send(client,"/api/auth/login",{"email":"unknown@example.test","password":"Wrong-password!"},headers={"X-Forwarded-For":f"192.0.2.{i}"}).status_code==401
    assert send(client,"/api/auth/login",{"email":"unknown@example.test","password":"Wrong-password!"}).status_code==429


def test_catalog_hides_links_and_has_download_indicator(client):
    result=send(client,"/api/contenido",{"limit":10000})
    assert result.status_code==200
    row=result.json["data"][0]
    assert row["has_download"] is True
    assert "descarga" not in row and "enlace_canal" not in row
    assert "mediafire" not in result.get_data(as_text=True)


def test_download_membership_checked_without_cron(client,system):
    assert send(client,"/api/download/1",method="GET").status_code==401
    tg_login(client)
    assert send(client,"/api/download/1",method="GET").json["host"]=="www.mediafire.com"
    system.supabase_service.rows["usuarios"][0]["fecha_vencimiento"]="2020-01-01T00:00:00+00:00"
    assert send(client,"/api/download/1",method="GET").status_code==403
    assert send(client,"/api/playback/1",method="GET").status_code==403


@pytest.mark.parametrize("url",["javascript:alert(1)","http://mediafire.com/a","https://localhost/a","https://user:pass@mediafire.com/a", "https://mediafire.com\\@evil.example/a"])
def test_download_rejects_unsafe_urls(client,system,url):
    tg_login(client)
    system.supabase_service.rows["contenido"][0]["descarga"]=url
    assert send(client,"/api/download/1",method="GET").status_code==404


def test_playback_is_authorized_and_public_key_retired(client):
    assert send(client,"/api/playback/1",method="GET").status_code==401
    tg_login(client)
    assert send(client,"/api/playback/1",method="GET").json["embed"] is True
    assert send(client,"/api/config/vimeus_key",method="GET").status_code==410


def test_cron_and_telegram_webhook_require_secrets(client,system):
    assert send(client,"/cron/verificar_vencimientos",method="GET").status_code==401
    assert send(client,"/cron/verificar_vencimientos?secret="+os.environ["CRON_SECRET"],method="GET").status_code==401
    assert send(client,"/cron/verificar_vencimientos",method="GET",headers={"Authorization":"Bearer "+os.environ["CRON_SECRET"]}).status_code==200
    assert send(client,"/"+os.environ["BOT_TOKEN"],{}).status_code==401


def test_host_and_json_validation(client):
    assert client.get("/health",base_url="http://evil.example").status_code==403
    assert send(client,"/api/auth/login",[]).status_code==400
    assert send(client,"/api/contenido",{"limit":"invalid"}).status_code==400


def test_local_html_has_no_production_api_or_telegram_cdn(client):
    for path in ["/", "/cuenta"]:
        html=send(client,path,method="GET").get_data(as_text=True)
        assert 'src="https://' not in html
    js=send(client,"/static/app.js",method="GET").get_data(as_text=True)
    assert 'const API_BASE_URL = ""' in js


def test_sqlite_forbidden_in_production(tmp_path):
    with pytest.raises(RuntimeError):
        SecurityStore("sqlite:///"+str(tmp_path/"wrong.sqlite"),local=False)


def test_postgres_without_tls_is_rejected_before_connecting():
    with pytest.raises(RuntimeError,match="TLS"):
        SecurityStore("postgresql+psycopg://local:unused@example.invalid/db",local=False)


def test_concurrent_payment_claim(system):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:system.security_store.claim_event("same-purchase"), range(8)))
    assert results.count("new")==1


def test_paypal_missing_verification_config_fails_closed(client,system):
    assert system.paypal_verificar_webhook({},b'{}') is False
    response=send(client,"/webhook/paypal",{"event_type":"PAYMENT.CAPTURE.COMPLETED"})
    assert response.status_code==400
