import pytest


@pytest.mark.parametrize('path', ['/', '/cuenta', '/membresia', '/instalar'])
def test_public_measurement_pages_allow_only_required_google_endpoints(client, path):
    response = client.get(path)
    policy = response.headers['Content-Security-Policy']
    assert 'https://www.googletagmanager.com' in policy
    assert 'https://*.google-analytics.com' in policy
    assert "object-src 'none'" in policy
    assert "form-action 'self'" in policy


@pytest.mark.parametrize('path', ['/api/auth/me', '/admin', '/tv', '/tv/vincular'])
def test_other_surfaces_keep_existing_network_restrictions(client, path):
    policy = client.get(path).headers['Content-Security-Policy']
    assert 'googletagmanager' not in policy
    assert 'google-analytics' not in policy
    assert "connect-src 'self';" in policy
