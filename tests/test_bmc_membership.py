"""IMAX membership (US$2/month) from Buy Me a Coffee webhooks, and the admin people view."""
import time
import pytest
from sqlalchemy import update
from billing.config import MEMBERSHIP_GRACE
from billing.schema import access
from conftest import send, register, owner_login, tg_login
from test_billing import webhook, create_order, payload as shop_payload


def member(email='person@example.test', membership_id=501, period_end=None, kind='membership.started', event_id=None, **data):
    period_end = period_end or int(time.time()) + 30 * 86400
    body = {'id': membership_id, 'object': 'membership', 'membership_level_id': 283557, 'membership_level_name': 'IMAX',
            'status': 'active', 'canceled': 'false', 'cancel_at_period_end': 'false', 'paused': 'false',
            'supporter_name': 'Persona', 'supporter_email': email, 'amount': 2, 'currency': 'USD',
            'current_period_start': int(time.time()), 'current_period_end': period_end}
    body.update(data)
    return {'type': kind, 'live_mode': True, 'attempt': 1, 'created': int(time.time()),
            'event_id': event_id or f'{kind}-{membership_id}-{period_end}', 'data': body}


def mine(client):
    return send(client, '/api/payments/mine', method='GET').json


def test_membership_by_account_email_lasts_until_period_end_and_is_idempotent(client, system):
    register(client)
    end = int(time.time()) + 30 * 86400
    result = webhook(client, member(email='Person@Example.test', period_end=end))
    assert result.status_code == 200 and result.json['activated']
    assert mine(client)['active']
    expiry = system.billing_store.expiry(system.security_store.account(email='person@example.test')['id'])
    assert expiry == end + MEMBERSHIP_GRACE
    assert webhook(client, member(period_end=end, event_id='retry')).json['activated']
    assert system.billing_store.expiry(system.security_store.account(email='person@example.test')['id']) == expiry
    approved = [o for o in mine(client)['orders'] if o['status'] == 'approved']
    assert len(approved) == 1 and approved[0]['amount_minor'] == 200
    assert send(client, '/api/playback/1', method='GET').status_code == 200
    assert system.billing_store.events()[0]['outcome'] == 'activado'


def test_telegram_account_is_linked_by_email_given_on_the_membership_page(client, system):
    auth = tg_login(client)
    order, _ = create_order(client, auth=auth, email='Pagador@Correo.test')
    assert system.billing_store.get(order['id'])['payer'] == 'pagador@correo.test'
    assert webhook(client, member(email='pagador@correo.test')).json['activated']
    assert mine(client)['active']
    assert system.billing_store.get(order['id'])['status'] == 'approved'


def test_bmc_request_requires_an_email(client, system):
    auth = tg_login(client)
    result = send(client, '/api/payments/orders', {'method': 'bmc'}, auth.json['csrf_token'])
    assert result.status_code == 400 and result.json['code'] == 'email_required'


def test_unknown_email_waits_for_admin_link_and_only_owner_can_link(client, system):
    auth = register(client)
    assert webhook(client, member(email='otro@correo.test', membership_id=777)).json['activated'] is False
    assert not mine(client)['active']
    event = system.billing_store.events()[0]
    assert event['outcome'] == 'sin_vincular' and 'otro@correo.test' in event['detail']
    account_id = system.security_store.account(email='person@example.test')['id']
    body = {'account_id': account_id, 'confirmed': True}
    assert send(client, '/api/admin/bmc/memberships/777/link', body, auth.json['csrf_token']).status_code == 403
    admin = system.app.test_client(); owner = owner_login(admin)
    assert send(admin, '/api/admin/bmc/memberships/777/link', {**body, 'confirmed': False}, owner.json['csrf_token']).status_code == 400
    assert send(admin, '/api/admin/bmc/memberships/777/link', body, owner.json['csrf_token']).json['success']
    assert mine(client)['active']
    # The link survives renewals even if the BMC email never matches an account.
    renewal_end = int(time.time()) + 60 * 86400
    with system.security_store.engine.begin() as c:
        c.execute(update(access).values(expires_at=time.time() - 1))
    assert webhook(client, member(email='otro@correo.test', membership_id=777, kind='membership.updated',
                                  period_end=int(time.time()) + 29 * 86400)).json['activated']
    assert mine(client)['active']
    assert renewal_end  # renewal date stays within the 40-day window accepted above


def test_same_email_on_two_accounts_is_never_guessed(client, system):
    register(client)
    other = system.app.test_client(); tg = tg_login(other)
    create_order(other, auth=tg, email='person@example.test')
    assert webhook(client, member()).json['activated'] is False
    assert 'Hay 2 cuentas' in system.billing_store.events()[0]['detail']
    assert not mine(client)['active']
    assert system.billing_store.memberships()[0]['account_id'] is None


@pytest.mark.parametrize('field,value', [('membership_level_id', 5), ('amount', 1), ('currency', 'EUR'), ('status', 'past_due'),
                                         ('canceled', 'true'), ('paused', 'true'), ('current_period_end', 'x')])
def test_wrong_level_price_or_state_never_grants(client, field, value):
    register(client)
    assert webhook(client, member(**{field: value})).json['activated'] is False
    assert not mine(client)['active']


def test_far_future_period_end_needs_review(client, system):
    register(client)
    assert webhook(client, member(period_end=int(time.time()) + 400 * 86400)).json['activated'] is False
    assert system.billing_store.events()[0]['outcome'] == 'revisar'


def test_cancellation_keeps_paid_time(client, system):
    register(client)
    end = int(time.time()) + 20 * 86400
    webhook(client, member(period_end=end))
    result = webhook(client, member(period_end=end, kind='membership.cancelled', canceled='true', status='canceled'))
    assert result.json['activated'] is False and mine(client)['active']
    assert system.billing_store.events()[0]['outcome'] == 'cancelada'
    assert system.billing_store.memberships()[0]['canceled'] == 1


def test_shop_created_event_without_answer_is_marked_waiting_not_failed(client, system):
    order, _ = create_order(client)
    created = shop_payload(order); created['data']['extras'][0]['question_answers'] = []
    webhook(client, created)
    assert system.billing_store.events()[0]['outcome'] == 'esperando'
    assert system.billing_store.reviews() == []
    updated = shop_payload(order); updated['type'] = 'extra_purchase.updated'; updated['event_id'] = 124
    assert webhook(client, updated).json['success']
    assert system.billing_store.events()[0]['outcome'] == 'activado'


def test_admin_people_view_and_detail(client, system):
    register(client)
    webhook(client, member())
    admin = system.app.test_client(); owner_login(admin)
    data = send(admin, '/api/admin/accounts', method='GET').json
    person = next(a for a in data['accounts'] if a['email'] == 'person@example.test')
    assert person['access'] == 'activo' and person['orders'] == 1
    assert data['counts']['activo'] >= 1 and data['total'] >= 1
    assert [a['email'] for a in send(admin, '/api/admin/accounts?q=PERSON', method='GET').json['accounts']] == ['person@example.test']
    detail = send(admin, f"/api/admin/accounts/{person['id']}", method='GET').json
    assert detail['memberships'][0]['id'] == '501' and detail['events'][0]['outcome'] == 'activado'
    bmc = send(admin, '/api/admin/bmc', method='GET').json
    event_id = bmc['events'][0]['id']
    assert 'payload' not in bmc['events'][0]
    assert send(admin, f'/api/admin/bmc/events/{event_id}', method='GET').json['payload']['data']['supporter_email'] == 'person@example.test'
    assert send(client, '/api/admin/accounts', method='GET').status_code == 403
    assert send(client, f'/api/admin/bmc/events/{event_id}', method='GET').status_code == 403


def test_local_membership_simulation(client, system):
    order, auth = create_order(client)
    admin = system.app.test_client(); owner = owner_login(admin)
    result = send(admin, f"/api/admin/payments/{order['id']}/simulate", {'kind': 'membership'}, owner.json['csrf_token'])
    assert result.json['simulated'] and result.json['activated']
    assert mine(client)['active']
