import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, update, event
from billing.schema import orders, access, receipts, review_events
from conftest import send, register, owner_login, tg_login, ORIGIN


def create_order(client, method='bmc', auth=None, **extra):
    auth = auth or register(client)
    response = send(client, '/api/payments/orders', {'method':method, **extra}, auth.json['csrf_token'])
    assert response.status_code == 200, response.json
    return response.json['order'], auth


def payload(order, payment_id=1001):
    return {'event_id':123,'type':'extra_purchase.created','live_mode':True,'created':int(time.time()),
        'data':{'id':payment_id,'status':'succeeded','refunded':'false','amount':1.50,'currency':'USD',
                'supporter_email':'unrelated@example.test','extras':[{'id':517243,'amount':'1.50','currency':'USD','quantity':1,'question_answers':[order['code']]}]}}


def webhook(client, data, signed=True):
    raw=json.dumps(data).encode()
    signature=hmac.new(os.environ['BMC_WEBHOOK_SECRET'].encode(),raw,hashlib.sha256).hexdigest() if signed else 'bad'
    return client.post('/webhook/buymeacoffee',data=raw,content_type='application/json',headers={'x-signature-sha256':signature},base_url=ORIGIN)


def report(client, order, auth, ref='OP123456'):
    return send(client,f'/api/payments/orders/{order["id"]}/report',
        {'reference':ref,'payer':'Persona de prueba','paid_date':'2026-10-26'},auth.json['csrf_token'])


def approve(admin, order, auth):
    return send(admin,f'/api/admin/payments/{order["id"]}/decide',{'decision':'approve','confirmed':True},auth.json['csrf_token'])


def test_single_plan_three_fixed_prices_and_missing_binance_qr(client):
    plans=send(client,'/api/planes',method='GET').json
    assert len(plans)==1 and plans[0]['precio_dolares']==1.5 and plans[0]['precio_soles']==5.5
    assert plans[0]['duracion_dias']==30 and plans[0]['renovacion_automatica'] is False
    config=send(client,'/api/payments/config',method='GET').json
    assert [(m['id'],m['amount_minor'],m['currency']) for m in config['methods']] == [('bmc',150,'USD'),('yape_plin',550,'PEN'),('binance',150,'USDT')]
    assert config['methods'][1]['available'] and not config['methods'][2]['available']


def test_pending_requests_survive_history_limit(client, system):
    order, _ = create_order(client, 'yape_plin')
    account_id = system.billing_store.get(order['id'])['account_id']
    rows = [dict(id=f'history-{i}', code=f'OLD-{i}', account_id=account_id,
                 method='yape_plin', amount_minor=550, currency='PEN', days=30,
                 status='rejected', created_at=time.time()+i+1, updated_at=time.time())
            for i in range(101)]
    with system.billing_store.engine.begin() as connection:
        connection.execute(orders.insert(), rows)
    assert order['id'] in {row['id'] for row in system.billing_store.history()}
    assert order['id'] in {row['id'] for row in system.billing_store.history(account_id)}


def test_prices_days_and_user_identity_cannot_be_overridden(client, system):
    order,_=create_order(client,'yape_plin',amount_minor=1,currency='USD',days=365,account_id='someone-else',plan='diamond')
    stored=system.billing_store.get(order['id'])
    assert stored['amount_minor']==550 and stored['currency']=='PEN' and stored['days']==30
    assert stored['account_id']==system.security_store.account(email='person@example.test')['id']


def test_manual_report_does_not_activate_and_owner_can_approve_once(client, system):
    order,auth=create_order(client,'yape_plin')
    assert report(client,order,auth).status_code==200
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False
    assert send(client,'/api/download/1',method='GET').status_code==403
    admin=system.app.test_client(); owner=owner_login(admin)
    assert approve(client,order,auth).status_code==403
    missing=send(admin,f'/api/admin/payments/{order["id"]}/decide',{'decision':'approve'},owner.json['csrf_token'])
    assert missing.status_code==400
    before=time.time();result=approve(admin,order,owner)
    assert result.status_code==200
    expiry=result.json['order']['expires_at']
    assert before+30*86400 <= expiry <= time.time()+30*86400
    assert approve(admin,order,owner).json['order']['expires_at']==expiry
    assert send(client,'/api/download/1',method='GET').json['host']=='www.mediafire.com'
    assert send(client,'/api/playback/1',method='GET').status_code==200
    assert system.bot.calls==[]


def test_manual_rejection_reason_and_no_access(client, system):
    order,auth=create_order(client,'yape_plin');report(client,order,auth)
    admin=system.app.test_client();owner=owner_login(admin)
    result=send(admin,f'/api/admin/payments/{order["id"]}/decide',{'decision':'reject','reason':'No aparece el ingreso. Revisa tu número de operación.'},owner.json['csrf_token'])
    assert result.status_code==200 and result.json['order']['status']=='rejected'
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False
    assert approve(admin,order,owner).status_code==409


def test_different_accounts_cannot_approve_the_same_operation(client, system):
    first,auth=create_order(client,'yape_plin');report(client,first,auth,'OP-12345')
    other=system.app.test_client();second,otherauth=create_order(other,'yape_plin',register(other,'other@example.test'));report(other,second,otherauth,'OP12345')
    admin=system.app.test_client();owner=owner_login(admin)
    assert approve(admin,first,owner).status_code==200
    assert approve(admin,second,owner).status_code==409
    assert send(other,'/api/payments/mine',method='GET').json['active'] is False


def test_own_orders_only_and_csrf(client, system):
    first,auth=create_order(client,'yape_plin')
    other=system.app.test_client();otherauth=register(other,'other@example.test')
    assert report(other,first,otherauth).status_code==404
    assert send(other,'/api/payments/mine',method='GET').json['orders']==[]
    assert send(client,'/api/payments/orders',{'method':'yape_plin'}).status_code==403
    assert send(other,'/api/admin/payments',method='GET').status_code==403


def test_double_click_reuses_pending_order_and_report(client):
    first,auth=create_order(client,'yape_plin')
    second,_=create_order(client,'yape_plin',auth)
    assert first['id']==second['id']
    assert report(client,first,auth).status_code==200
    assert report(client,first,auth).status_code==200
    assert len(send(client,'/api/payments/mine',method='GET').json['orders'])==1


def test_web_account_bmc_signed_activation_and_replay(client, system):
    order,_=create_order(client)
    response=webhook(client,payload(order))
    assert response.status_code==200 and response.json['success']
    stored=system.billing_store.get(order['id']);expiry=stored['expires_at']
    assert webhook(client,payload(order)).json['duplicate'] is True
    assert system.billing_store.get(order['id'])['expires_at']==expiry
    assert send(client,'/api/payments/mine',method='GET').json['active']
    assert send(client,'/api/download/1',method='GET').status_code==200
    assert system.bot.calls==[]


@pytest.mark.parametrize('field,value', [('amount',3.50),('amount',0),('amount','NaN'),('currency','PEN'),('status','pending'),('refunded','true')])
def test_webhook_mismatch_queues_review_without_access(client, system, field, value):
    order,_=create_order(client);data=payload(order);data['data'][field]=value
    result=webhook(client,data)
    assert result.json['review'] and result.json['activated'] is False
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False
    assert system.billing_store.reviews()


def test_signature_and_test_events_never_activate(client):
    order,_=create_order(client)
    assert webhook(client,payload(order),False).status_code==401
    data=payload(order);data['live_mode']=False
    assert webhook(client,data).json['test_event']
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False


@pytest.mark.parametrize('settled', ['1.4850', '1.49', '1.51'])
def test_signed_purchase_preserves_fixed_price_with_small_settlement_variance(client, system, settled):
    order,_=create_order(client);data=payload(order);data['data']['amount']=settled
    result=webhook(client,data)
    assert result.json['success']
    stored=system.billing_store.get(order['id'])
    assert stored['amount_minor']==150 and stored['currency']=='USD'
    assert webhook(client,data).json['duplicate'] is True


@pytest.mark.parametrize('field,value', [('amount','1.00'),('amount',None),('amount','NaN'),('currency','PEN')])
def test_product_price_and_currency_must_match_even_if_total_matches(client, field, value):
    order,_=create_order(client);data=payload(order);data['data']['extras'][0][field]=value
    assert webhook(client,data).json['review']
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False


@pytest.mark.parametrize('settled', ['1.46', '1.54', '0.01', 'Infinity'])
def test_larger_settlement_difference_requires_review(client, settled):
    order,_=create_order(client);data=payload(order);data['data']['amount']=settled
    assert webhook(client,data).json['review']
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False


def test_email_only_or_wrong_order_code_is_never_matched(client):
    order,_=create_order(client);data=payload(order)
    data['data']['supporter_email']='person@example.test'
    for code in ('', 'QH-'+'F'*20):
        data['data']['extras'][0]['question_answers']=[code]
        assert webhook(client,data).json['review']
        assert send(client,'/api/payments/mine',method='GET').json['active'] is False


@pytest.mark.parametrize('kind',['membership.started','recurring_donation.started','extra_purchase.refunded'])
def test_subscriptions_and_refunds_do_not_extend_access(client, system, kind):
    order,_=create_order(client);data=payload(order);data['type']=kind
    assert webhook(client,data).json['activated'] is False
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False
    assert system.billing_store.reviews()


def test_provider_payment_cannot_be_reused_for_another_account(client, system):
    first,_=create_order(client);assert webhook(client,payload(first)).json['success']
    other=system.app.test_client();second,_=create_order(other,auth=register(other,'other@example.test'))
    assert webhook(other,payload(second)).json['review']
    assert send(other,'/api/payments/mine',method='GET').json['active'] is False


def test_renewal_adds_exactly_30_days_and_expiry_blocks_playback(client, system):
    first,auth=create_order(client);webhook(client,payload(first));original=system.billing_store.get(first['id'])['expires_at']
    second,_=create_order(client,auth=auth);webhook(client,payload(second,1002))
    assert system.billing_store.get(second['id'])['expires_at']==original+30*86400
    with system.security_store.engine.begin() as c:c.execute(update(access).values(expires_at=time.time()-1))
    assert send(client,'/api/payments/mine',method='GET').json['active'] is False
    assert send(client,'/api/playback/1',method='GET').status_code==403
    assert send(client,'/api/download/1',method='GET').status_code==403


def test_existing_telegram_time_is_preserved(client, system):
    auth=tg_login(client);order,_=create_order(client,auth=auth)
    baseline=system.legacy_access_expiry(900000001)
    webhook(client,payload(order))
    assert system.billing_store.get(order['id'])['expires_at']==baseline+30*86400


def test_concurrent_confirmations_only_grant_once(client, system):
    order,_=create_order(client)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda _:system.billing_store.decide(order['id'],True,provider_reference='1001'),range(6)))
    assert len({r['expires_at'] for r in results})==1
    assert sum(bool(r.get('duplicate')) for r in results)==5


def test_atomic_failure_rolls_back_receipt_order_and_access(client, system):
    order,_=create_order(client)
    def fail(conn,cursor,statement,parameters,context,executemany):
        if 'paid_access' in statement and 'INSERT' in statement:raise RuntimeError('injected storage failure')
    event.listen(system.security_store.engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError):system.billing_store.decide(order['id'],True,provider_reference='1001')
    finally:event.remove(system.security_store.engine,'before_cursor_execute',fail)
    assert system.billing_store.get(order['id'])['status']=='pending_provider'
    with system.security_store.engine.connect() as c:assert c.execute(select(receipts)).all()==[]
    assert webhook(client,payload(order)).json['success']


def test_qr_upload_admin_only_and_enables_binance_then_manual_approval(client, system):
    raw=(Path(__file__).resolve().parents[1]/'static/qr-yape.png').read_bytes()
    body={'method':'binance','recipient':'Receptor de prueba','confirmed':True,'data':base64.b64encode(raw).decode()}
    auth=register(client)
    assert send(client,'/api/admin/payments/qr',body,auth.json['csrf_token']).status_code==403
    admin=system.app.test_client();owner=owner_login(admin)
    assert send(admin,'/api/admin/payments/qr',{**body,'data':base64.b64encode(b'<svg onload="evil()"/>').decode()},owner.json['csrf_token']).status_code==400
    assert send(admin,'/api/admin/payments/qr',body,owner.json['csrf_token']).status_code==200
    image=send(client,'/api/payments/qr/binance',method='GET')
    assert image.data==raw and image.content_type=='image/png'
    order,_=create_order(client,'binance',auth);assert report(client,order,auth,'BN123456789').status_code==200
    assert approve(admin,order,owner).status_code==200
    assert send(client,'/api/download/1',method='GET').status_code==200


def test_existing_yape_qr_kept_byte_for_byte(client):
    original=(Path(__file__).resolve().parents[1]/'static/qr-yape.png').read_bytes()
    assert send(client,'/api/payments/qr/yape_plin',method='GET').data==original


def test_local_bmc_never_opens_real_checkout_and_simulator_is_admin_only(client, system):
    order,auth=create_order(client)
    result=send(client,'/api/payments/orders',{'method':'bmc'},auth.json['csrf_token'])
    assert result.json['checkout_url'] is None and result.json['local']
    assert send(client,f'/api/admin/payments/{order["id"]}/simulate',{},auth.json['csrf_token']).status_code==403
    admin=system.app.test_client();owner=owner_login(admin)
    assert send(admin,f'/api/admin/payments/{order["id"]}/simulate',{},owner.json['csrf_token']).json['simulated']
    system.app.config['SECURITY_LOCAL']=False
    try:assert send(admin,f'/api/admin/payments/{order["id"]}/simulate',{},owner.json['csrf_token']).status_code==404
    finally:system.app.config['SECURITY_LOCAL']=True


def test_missing_qr_disables_binance_and_old_paypal_checkout_is_retired(client):
    auth=owner_login(client)
    assert send(client,'/api/payments/orders',{'method':'binance'},auth.json['csrf_token']).status_code==409
    assert send(client,'/api/admin/marketing/crear_pago_paypal',{'plan':'diamond'},auth.json['csrf_token']).status_code==410


def test_membership_page_has_no_discount_or_tutorial_or_paypal(client):
    page=send(client,'/membresia',method='GET')
    assert page.status_code==200
    text=page.text.lower()
    assert 'sin renovación automática' in text
    for word in ('oferta especial','qh50off','50%','videotutorial','paypal','player.vimeo.com'):
        assert word not in text
    assert 'src="https://' not in text
    script=send(client,'/static/app.js',method='GET').text
    assert 'verTutorialYape' not in script and 'iniciarContadorOferta' not in script
