"""Test the MTN MoMo gateway connection.

Sends a tiny (1 XAF) request-to-pay so you can confirm your credentials work
and watch the payment appear/approve in the MoMo developer sandbox.

Usage:
    python manage.py test_momo 6XXXXXXXX
    python manage.py test_momo 46733123454   # (or your sandbox test MSISDN)

If no phone is given it uses a common MTN sandbox test number.
"""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Verify MTN MoMo API credentials by sending a tiny request-to-pay'

    def add_arguments(self, parser):
        parser.add_argument('phone', nargs='?', default='', help='MoMo/MSISDN to send the 1 XAF request to')

    def handle(self, *args, **options):
        from articles.momo import MomoClient, MomoNotConfigured, MomoError

        phone = options['phone'] or getattr(settings, 'MOMO_TEST_MSISDN', '46733123454')

        if not all([settings.MOMO_API_USER, settings.MOMO_API_KEY, settings.MOMO_SUBSCRIPTION_KEY]):
            raise CommandError(
                'MTN MoMo credentials are not set. Add to .env (or the hosting env):\n'
                '  MOMO_API_USER=<your API user UUID>\n'
                '  MOMO_API_KEY=<your API key>\n'
                '  MOMO_SUBSCRIPTION_KEY=<your Primary/Subscription key>\n'
                'Get them free at https://momodeveloper.mtn.com (sandbox).'
            )

        self.stdout.write(f'Target environment: {settings.MOMO_TARGET_ENVIRONMENT}')
        self.stdout.write(f'Base URL: {settings.MOMO_BASE_URL}')
        self.stdout.write(f'Callback URL: {settings.MOMO_CALLBACK_URL}')
        self.stdout.write(f'Sending 1 XAF request-to-pay to {phone}...')

        try:
            client = MomoClient()
        except MomoNotConfigured as exc:
            raise CommandError(str(exc))

        try:
            ref, status = client.request_to_pay(
                amount=1,
                phone_number=phone,
                external_id='MOMO-TEST-' + __import__('uuid').uuid4().hex[:12].upper(),
                payer_message='MoMo gateway connection test',
                payee_note='test',
            )
        except MomoError as exc:
            self.stdout.write(self.style.ERROR(f'request_to_pay FAILED: {exc}'))
            raise CommandError('Double-check MOMO_API_USER / MOMO_API_KEY / MOMO_SUBSCRIPTION_KEY '
                               'and that the target environment matches your subscription.')

        self.stdout.write(self.style.SUCCESS(f'request_to_pay accepted (HTTP {status}) — ref {ref}'))
        self.stdout.write('Now approve the 1 XAF transaction in the MoMo developer sandbox '
                          '(Sandbox User view), then press Enter to check its status.')

        import sys
        try:
            input('Press Enter when the payment has been approved in the sandbox...')
        except EOFError:
            pass

        try:
            data = client.get_transaction_status(ref)
        except MomoError as exc:
            self.stdout.write(self.style.ERROR(f'Status check failed: {exc}'))
            return

        self.stdout.write(f'Gateway status payload: {data}')
        status = (data.get('status') or '').upper()
        if status == 'SUCCESSFUL':
            self.stdout.write(self.style.SUCCESS('✅ Connection verified — payment approved and confirmed.'))
        else:
            self.stdout.write(self.style.WARNING(f'Payment status is "{status}". '
                                                 'Approve it in the sandbox and run again.'))
