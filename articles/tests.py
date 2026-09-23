from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from .models import Article, ArticlePurchase, CoAuthor


# Use plain static-files storage in tests (the production manifest storage
# requires `collectstatic` to have run, which isn't the case in tests).
@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class EditorPaymentRequestTests(TestCase):
    """Editors confirm reader payments from the dashboard to unlock articles."""

    def setUp(self):
        self.editor = CustomUser.objects.create_user(
            username='editor1', password='editor-pass-123', role='editor')
        self.author = CustomUser.objects.create_user(
            username='author1', password='author-pass-123', role='author')
        self.reader = CustomUser.objects.create_user(
            username='reader1', password='reader-pass-123', role='author')
        self.article = Article.objects.create(
            title='Deep Learning in WSNs', abstract='Abstract', content='Full text',
            author=self.author, status='published', published_date=timezone.now(),
        )
        self.purchase = ArticlePurchase.objects.create(
            article=self.article, user=self.reader, amount=2000,
            phone_number='670000000', provider='mtn_momo', reference='PAY-2026-0001',
        )

    def test_reader_has_no_access_before_confirmation(self):
        self.client.login(username='reader1', password='reader-pass-123')
        response = self.client.get(reverse('article_detail', args=[self.article.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_view_full'])

    def test_editor_sees_pending_request(self):
        self.client.login(username='editor1', password='editor-pass-123')
        response = self.client.get(reverse('editor_payment_requests'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PAY-2026-0001')
        self.assertContains(response, '670000000')
        self.assertContains(response, 'reader1')

    def test_non_editor_cannot_open_payment_requests(self):
        self.client.login(username='reader1', password='reader-pass-123')
        response = self.client.get(reverse('editor_payment_requests'))
        self.assertEqual(response.status_code, 302)

    def test_editor_confirm_unlocks_article(self):
        self.client.login(username='editor1', password='editor-pass-123')
        response = self.client.post(
            reverse('editor_confirm_payment', args=[self.purchase.pk]))
        self.assertRedirects(response, reverse('editor_payment_requests'))

        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, 'paid')
        self.assertIsNotNone(self.purchase.paid_at)

        self.client.logout()
        self.client.login(username='reader1', password='reader-pass-123')
        response = self.client.get(reverse('article_detail', args=[self.article.pk]))
        self.assertTrue(response.context['can_view_full'])

    def test_editor_fail_keeps_article_locked(self):
        self.client.login(username='editor1', password='editor-pass-123')
        response = self.client.post(
            reverse('editor_fail_payment', args=[self.purchase.pk]))
        self.assertRedirects(response, reverse('editor_payment_requests'))

        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, 'failed')

        self.client.logout()
        self.client.login(username='reader1', password='reader-pass-123')
        response = self.client.get(reverse('article_detail', args=[self.article.pk]))
        self.assertFalse(response.context['can_view_full'])

    def test_get_request_does_not_confirm_payment(self):
        self.client.login(username='editor1', password='editor-pass-123')
        self.client.get(reverse('editor_confirm_payment', args=[self.purchase.pk]))
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, 'pending')

    def test_editor_dashboard_shows_payment_card(self):
        self.client.login(username='editor1', password='editor-pass-123')
        response = self.client.get(reverse('editor_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment Requests')


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ArticleAuthorsTests(TestCase):
    """All authors (submitting author + co-authors) appear on published articles."""

    def setUp(self):
        self.author = CustomUser.objects.create_user(
            username='mainauthor', password='pass-main-123', role='author',
            first_name='Marie', last_name='Nkeng')
        self.article = Article.objects.create(
            title='Network Security in Practice', abstract='Abstract',
            content='Full text', author=self.author, status='published',
            published_date=timezone.now(),
        )
        CoAuthor.objects.create(
            article=self.article, name='John Doe', email='john@example.com',
            affiliation='University of Bamenda')
        CoAuthor.objects.create(
            article=self.article, name='Alice Mbah', email='alice@example.com')

    def test_published_listing_shows_every_author_name(self):
        response = self.client.get(reverse('published_articles'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marie Nkeng')
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Alice Mbah')

    def test_journal_hub_shows_every_author_name(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marie Nkeng')
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Alice Mbah')

    def test_article_page_shows_all_authors_to_visitors(self):
        response = self.client.get(reverse('article_detail', args=[self.article.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marie Nkeng')
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Alice Mbah')

    def test_pdf_author_line_includes_coauthors(self):
        from .journal_pdf import _author_line_and_affiliations
        line, affiliations = _author_line_and_affiliations(self.article)
        self.assertIn('Marie Nkeng', line)
        self.assertIn('John Doe', line)
        self.assertIn('Alice Mbah', line)
        self.assertIn('University of Bamenda', affiliations)

    def test_submission_saves_many_coauthors(self):
        self.client.login(username='mainauthor', password='pass-main-123')
        response = self.client.post(reverse('create_article'), {
            'title': 'Fresh Manuscript',
            'abstract': 'Short abstract',
            'content': 'Body text',
            'keywords': 'testing',
            'co_authors-TOTAL_FORMS': '3',
            'co_authors-INITIAL_FORMS': '0',
            'co_authors-MIN_NUM_FORMS': '0',
            'co_authors-MAX_NUM_FORMS': '1000',
            'co_authors-0-name': 'First Co',
            'co_authors-0-email': 'c1@example.com',
            'co_authors-0-affiliation': 'Uni A',
            'co_authors-1-name': 'Second Co',
            'co_authors-1-email': 'c2@example.com',
            'co_authors-2-name': 'Third Co',
            'co_authors-2-email': 'c3@example.com',
        })
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get(title='Fresh Manuscript')
        self.assertEqual(article.co_authors.count(), 3)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class JournalPageCtaTests(TestCase):
    """Join/submit call-to-action buttons on the journal pages."""

    def test_journal_hub_join_submit_button(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Join &amp; Submit Your Article')

    def test_author_guidelines_submit_cta(self):
        response = self.client.get(reverse('author_guidelines'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Submit Your Article')

    def test_about_page_submit_cta(self):
        response = self.client.get(reverse('journal_about'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Submit Your Article')

