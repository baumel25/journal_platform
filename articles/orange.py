"""Orange Money Web Payment (M Payment) client.

Orange Money is a *separate* operator from MTN with its own API. The collection
flow used by web merchants is the "Orange Money Web Payment / M Payment" API
(available in Cameroon):

    https://developer.orange.com/apis/om-webpay

IMPORTANT: unlike MTN's public sandbox, Orange exposes this API only to
registered, approved merchants (KYA / compliance with the local operator). The
exact base path, request fields and response fields below follow the widely
documented Web Payment contract, but you MUST confirm them against the
integration document Orange sends when your merchant application is approved,
and adjust this file if needed.

Configuration (via settings / .env):

    ORANGE_CLIENT_ID        - OAuth2 client id (from Orange Developer portal)
    ORANGE_CLIENT_SECRET    - OAuth2 client secret
    ORANGE_MERCHANT_KEY     - merchant key assigned at onboarding
    ORANGE_BASE_URL         - default https://api.orange.com
    ORANGE_COUNTRY_CODE     - ISO country code used in the path (default 'cm')
    ORANGE_NOTIF_URL        - callback URL Orange calls with the payment result

Until ORANGE_CLIENT_ID / ORANGE_CLIENT_SECRET / ORANGE_MERCHANT_KEY are set the
site uses a manual confirmation flow for Orange Money (instructions + editor
confirmation), so the pay page always works.
"""
import base64
import logging
import uuid

import requests

logger = logging.getLogger(__name__)


class OrangeError(Exception):
    """Base error for Orange Money API failures."""


class OrangeNotConfigured(OrangeError):
    """Raised when Orange Money API credentials are not configured."""


def _credentials_present():
    from django.conf import settings
    return all([
        getattr(settings, 'ORANGE_CLIENT_ID', ''),
        getattr(settings, 'ORANGE_CLIENT_SECRET', ''),
        getattr(settings, 'ORANGE_MERCHANT_KEY', ''),
    ])


def is_orange_configured():
    """Whether the Orange Money merchant credentials are present."""
    return _credentials_present()


class OrangeClient:
    """Thin client for the Orange Money Web Payment (collection) flow."""

    def __init__(self):
        from django.conf import settings
        if not _credentials_present():
            raise OrangeNotConfigured(
                'Orange Money credentials are missing (ORANGE_CLIENT_ID, '
                'ORANGE_CLIENT_SECRET, ORANGE_MERCHANT_KEY).'
            )
        self.client_id = settings.ORANGE_CLIENT_ID
        self.client_secret = settings.ORANGE_CLIENT_SECRET
        self.merchant_key = settings.ORANGE_MERCHANT_KEY
        self.base_url = (getattr(settings, 'ORANGE_BASE_URL', '') or
                         'https://api.orange.com').rstrip('/')
        self.country = getattr(settings, 'ORANGE_COUNTRY_CODE', 'cm')
        self.notif_url = getattr(settings, 'ORANGE_NOTIF_URL', '')
        self._token = None

    # ── helpers ────────────────────────────────────────────────────────────
    def _webpay_path(self, *parts):
        return f"{self.base_url}/orange-money-webpay/{self.country}/v1/{'/'.join(parts)}"

    # ── auth ───────────────────────────────────────────────────────────────
    def get_token(self, force=False):
        """OAuth2 client-credentials token."""
        if self._token and not force:
            return self._token
        raw = f"{self.client_id}:{self.client_secret}"
        resp = requests.post(
            f"{self.base_url}/oauth/v2/token",
            headers={
                'Authorization': 'Basic ' + base64.b64encode(raw.encode('utf-8')).decode('ascii'),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={'grant_type': 'client_credentials'},
            timeout=30,
        )
        if resp.status_code != 200:
            raise OrangeError(f'Failed to obtain Orange token: {resp.status_code} {resp.text}')
        self._token = resp.json().get('access_token')
        if not self._token:
            raise OrangeError('Orange token response did not include an access_token')
        return self._token

    # ── collection ─────────────────────────────────────────────────────────
    def create_payment(self, *, amount, order_id, return_url, cancel_url, notif_url=None, lang='en'):
        """Create a web payment and return (payment_url, notif_token).

        The reader is redirected to ``payment_url`` where they complete the
        payment (USSD OTP) and are returned to ``return_url``.
        """
        payload = {
            'merchant_key': self.merchant_key,
            'currency': 'XAF',
            'order_id': order_id,
            'amount': str(amount),
            'return_url': return_url,
            'cancel_url': cancel_url,
            'notif_url': notif_url or self.notif_url,
            'lang': lang,
        }
        url = self._webpay_path('webpayment')
        headers = {
            'Authorization': 'Bearer ' + self.get_token(),
            'Content-Type': 'application/json',
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise OrangeError(f'Network error during create_payment: {exc}') from exc

        if resp.status_code == 401:
            headers['Authorization'] = 'Bearer ' + self.get_token(force=True)
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

        if resp.status_code not in (200, 201):
            raise OrangeError(f'create_payment failed: {resp.status_code} {resp.text}')

        data = resp.json()
        payment_url = data.get('payment_url')
        notif_token = data.get('notif_token', '')
        if not payment_url:
            raise OrangeError(f'Orange response missing payment_url: {data}')
        return payment_url, notif_token

    def get_transaction_status(self, order_id, notif_token=''):
        """Return the status payload for an order id."""
        url = self._webpay_path('transaction', str(order_id))
        headers = {'Authorization': 'Bearer ' + self.get_token()}
        try:
            resp = requests.get(url, params={'notif_token': notif_token}, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise OrangeError(f'Network error during status check: {exc}') from exc
        if resp.status_code == 401:
            resp = requests.get(
                url, params={'notif_token': notif_token},
                headers={'Authorization': 'Bearer ' + self.get_token(force=True)},
                timeout=30,
            )
        if resp.status_code != 200:
            raise OrangeError(f'get_transaction_status failed: {resp.status_code} {resp.text}')
        return resp.json()


def new_order_id():
    """Return a fresh unique order id for an Orange web payment."""
    return 'JCSA-' + uuid.uuid4().hex[:20].upper()
