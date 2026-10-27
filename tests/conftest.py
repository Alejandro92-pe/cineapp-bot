import os
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

@pytest.fixture(scope="session")
def app_module(tmp_path_factory):
    path=tmp_path_factory.mktemp("cine-security")/"test.sqlite"
    os.environ.update(APP_MODE="local",APP_ORIGIN="http://127.0.0.1:5010",
        SECURITY_DATABASE_URL="sqlite:///"+path.as_posix(),BOT_TOKEN="123456:TEST_ONLY_TOKEN",
        SUPABASE_URL="",SUPABASE_KEY="",SUPABASE_SERVICE_KEY="",VIMEUS_VIEW_KEY="test-view-not-real",
        CRON_SECRET="test-cron-secret-"*3, TELEGRAM_WEBHOOK_SECRET="test-tg-secret-"*3,
        BMC_WEBHOOK_SECRET="test-bmc-secret-"*3,PAYPAL_WEBHOOK_ID="",
        BMC_MONTHLY_PRODUCT_ID="517243", BMC_MONTHLY_READY="false")
    from security import password_hash
    os.environ["ADMIN_PASSWORD_HASH"]=password_hash("Local-admin-test-2026!")
    import main
    main.app.config["TESTING"]=True
    return main

@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    import socket, smtplib
    def denied(*args,**kwargs):
        raise AssertionError("External network/email forbidden in tests")
    monkeypatch.setattr(socket.socket,"connect",denied)
    monkeypatch.setattr(smtplib,"SMTP",denied)

@pytest.fixture
def system(app_module):
    from security_store import metadata
    with app_module.security_store.engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            connection.execute(table.delete())
    app_module.supabase_service.reset()
    app_module.bot.calls.clear()
    return app_module

@pytest.fixture
def client(system):
    return system.app.test_client()

ORIGIN="http://127.0.0.1:5010"

def send(client,path,body=None,csrf=None,method="POST",headers=None):
    h={"Origin":ORIGIN,**(headers or {})}
    if csrf: h["X-CSRF-Token"]=csrf
    return client.open(path,method=method,json=body,headers=h,base_url=ORIGIN)

def register(client,email="person@example.test"):
    return send(client,"/api/auth/register",{"name":"Prueba","email":email,"password":"Local-user-test-2026!"})

def owner_login(client):
    return send(client,"/api/admin/login",{"admin_id":5824989040,"password":"Local-admin-test-2026!"})

def signed_telegram(user_id=900000001,age=0):
    import time,json,hmac,hashlib
    from urllib.parse import urlencode
    d={"auth_date":str(int(time.time())-age),"query_id":"test-query", "user":json.dumps({"id":user_id,"first_name":"Prueba"})}
    key=hmac.new(b"WebAppData",os.environ["BOT_TOKEN"].encode(),hashlib.sha256).digest()
    d["hash"]=hmac.new(key,"\n".join(f"{k}={v}" for k,v in sorted(d.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(d)

def tg_login(client,user_id=900000001):
    return send(client,"/api/auth/telegram",{"init_data":signed_telegram(user_id)})
