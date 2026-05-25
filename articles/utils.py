from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse

User = get_user_model()

def notify_editors_new_submission(article):
    """Notify all editors when an author submits an article for review."""
    editors = User.objects.filter(role='editor', is_active=True)
    editor_emails = [e.email for e in editors if e.email]
    
    if not editor_emails:
        return
    
    subject = f'[Instructor: Journal of Computer Science and Applications] New Article Submitted: {article.title}'
    message = f"""
A new article has been submitted for review.

Title: {article.title}
Author: {article.author.get_full_name() or article.author.username}
Abstract: {article.abstract[:200]}...

You can review it here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, editor_emails)


def notify_author_decision(article, decision):
    """Notify the author when an editor makes a decision on their article."""
    author = article.author
    if not author.email:
        return
    
    if decision == 'approved':
        subject = f'[Instructor: Journal of Computer Science and Applications] Article Approved: {article.title}'
        message = f"""
Congratulations! Your article has been approved for publication.

Title: {article.title}
Status: Approved

Your article will be published soon. You can view it here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    elif decision == 'rejected':
        subject = f'[Instructor: Journal of Computer Science and Applications] Article Update: {article.title}'
        message = f"""
Your article has been reviewed, and unfortunately it has been rejected.

Title: {article.title}
Status: Rejected

You can view the reviewer comments here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    else:
        return
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [author.email])
