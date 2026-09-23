"""Context processors — expose the journal's payment receiver numbers to all templates."""
from django.conf import settings


def payment_receivers(request):
    """Make the manager's MTN / Orange numbers available as template variables."""
    return {
        'payment_mtn_number': settings.PAYMENT_MTN_NUMBER,
        'payment_orange_number': settings.PAYMENT_ORANGE_NUMBER,
    }


def pending_payments(request):
    """Give editors a sidebar badge with the number of pending payment requests."""
    user = getattr(request, 'user', None)
    count = 0
    if user is not None and user.is_authenticated and user.is_editor():
        from articles.models import ArticlePurchase
        count = ArticlePurchase.objects.filter(status='pending').count()
    return {'pending_payment_count': count}
