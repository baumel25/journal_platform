"""MTN MoMo Open API client for the Collection (request-to-pay) payment flow.

The journal sells access to full published articles. Payments are collected
via MTN Mobile Money using the official MoMo Open API:

    https://momodeveloper.mtn.com

Configuration (via settings / .env):

    MOMO_API_USER            - MoMo API user id (UUID)
    MOMO_API_KEY             - MoMo API key
    MOMO_SUBSCRIPTION_KEY    - MoMo subscription key (primary)
    MOMO_BASE_URL            - API base URL. Defaults to the sandbox:
                               https://sandbox.momodeveloper.mtn.com
    MOMO_TARGET_ENVIRONMENT  - 'sandbox' or 'live' (default: 'sandbox')
    MOMO_CALLBACK_URL        - Publicly reachable callback URL that MTN MoMo
                               calls when the payment is completed.

If the credentials are missing the client raises ``MomoNotConfigured`` and the
views fall back to a manual confirmation flow, so the site still works before
the live gateway credentials are added.
"""
import base64
import logging
import uuid

import requests

logger = logging.getLogger(__name__)


class MomoError(Exception):
    """Base error for MoMo API failures."""


class MomoNotConfigured(MomoError):
    """Raised when MoMo API credentials are not configured."""


def _credentials_present():
    from django.conf import settings
    return all([
        getattr(settings, 'MOMO_API_USER', ''),
        getattr(settings, 'MOMO_API_KEY', ''),
        getattr(settings, 'MOMO_SUBSCRIPTION_KEY', ''),
    ])


class MomoClient:
    """Thin client for the MTN MoMo Collection API."""

    def __init__(self):
        from django.conf import settings
        if not _credentials_present():
            raise MomoNotConfigured(
                'MTN MoMo API credentials are missing (MOMO_API_USER, '
                'MOMO_API_KEY, MOMO_SUBSCRIPTION_KEY).'
            )
        self.api_user = settings.MOMO_API_USER
        self.api_key = settings.MOMO_API_KEY
        self.subscription_key = settings.MOMO_SUBSCRIPTION_KEY
        self.base_url = (getattr(settings, 'MOMO_BASE_URL', '') or
                         'https://sandbox.momodeveloper.mtn.com').rstrip('/')
        self.target_env = getattr(settings, 'MOMO_TARGET_ENVIRONMENT', 'sandbox')
        self.callback_url = getattr(settings, 'MOMO_CALLBACK_URL', '')
        self._token = None

    # ── auth ──────────────────────────────────────────────────────────────
    def _auth_header(self):
        raw = f"{self.api_user}:{self.api_key}"
        return 'Basic ' + base64.b64encode(raw.encode('utf-8')).decode('ascii')

    def get_token(self, force=False):
        if self._token and not force:
            return self._token
        resp = requests.post(
            f"{self.base_url}/collection/token/",
            headers={
                'Authorization': self._auth_header(),
                'Ocp-Apim-Subscription-Key': self.subscription_key,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise MomoError(f'Failed to obtain MoMo token: {resp.status_code} {resp.text}')
        self._token = resp.json().get('access_token')
        if not self._token:
            raise MomoError('MoMo token response did not include an access_token')
        return self._token

    # ── collection ────────────────────────────────────────────────────────
    def request_to_pay(self, *, amount, phone_number, external_id,
                       reference_id=None, payer_message='', payee_note=''):
        """Initiate a request-to-pay and return (reference_id, http_status)."""
        reference_id = reference_id or str(uuid.uuid4())
        payload = {
            'amount': str(amount),
            'currency': 'XAF',
            'externalId': external_id,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': str(phone_number),
            },
            'payerMessage': payer_message or 'Payment for journal article access',
            'payeeNote': payee_note or 'INSTRUCTOR JCSA full article unlock',
        }
        headers = self._headers(content_type='application/json')
        headers['X-Reference-Id'] = reference_id
        if self.callback_url:
            headers['X-Callback-Url'] = self.callback_url

        url = f"{self.base_url}/collection/v1_0/requesttopay"
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise MomoError(f'Network error during request_to_pay: {exc}') from exc

        if resp.status_code == 401:
            # Token may have expired — refresh once and retry.
            headers['Authorization'] = 'Bearer ' + self.get_token(force=True)
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

        if resp.status_code not in (200, 201, 202):
            raise MomoError(f'request_to_pay failed: {resp.status_code} {resp.text}')
        return reference_id, resp.status_code

    def get_transaction_status(self, reference_id):
        """Return the status payload of a request-to-pay transaction."""
        url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise MomoError(f'Network error during status check: {exc}') from exc

        if resp.status_code == 401:
            resp = requests.get(url, headers=self._headers(force_token=True), timeout=30)
        if resp.status_code != 200:
            raise MomoError(f'get_transaction_status failed: {resp.status_code} {resp.text}')
        return resp.json()

    # ── helpers ───────────────────────────────────────────────────────────
    def _headers(self, content_type=None, force_token=False):
        headers = {
            'Authorization': 'Bearer ' + self.get_token(force=force_token),
            'X-Target-Environment': self.target_env,
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers


def is_gateway_configured():
    """Whether the live MoMo gateway credentials are present."""
    return _credentials_present()
