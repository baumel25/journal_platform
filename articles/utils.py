from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


def notify_reviewer_invitation(invitation):
    """Send an email to the reviewer notifying them of a review invitation."""
    reviewer = invitation.reviewer
    if not reviewer.email:
        return

    subject = f'[Instructor: Journal of Computer Science and Applications] Review Invitation: {invitation.article.title}'
    accept_url = f'{settings.BASE_URL}{reverse("accept_invitation", args=[invitation.pk])}'
    decline_url = f'{settings.BASE_URL}{reverse("decline_invitation", args=[invitation.pk])}'
    dashboard_url = f'{settings.BASE_URL}{reverse("dashboard")}'

    message = f"""
Dear {reviewer.get_full_name() or reviewer.username},

You have been invited by editor {invitation.invited_by.get_full_name() or invitation.invited_by.username} to review the following article:

Title: {invitation.article.title}
Author: {invitation.article.author.get_full_name() or invitation.article.author.username}
Abstract: {invitation.article.abstract[:300]}...
Review Deadline: {invitation.deadline_days} days from acceptance
Access Level: {"Full Article" if invitation.access_level == "full" else "Abstract Only"}

{f'Message from the editor: {invitation.message}' if invitation.message else ''}

Please log in to your dashboard to accept or decline this invitation:

{dashboard_url}

Alternatively, you can use the following links:
- Accept: {accept_url}
- Decline: {decline_url}

Thank you for your contribution to the peer review process.

Best regards,
Instructor: Journal of Computer Science and Applications
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reviewer.email])


def notify_editor_invitation_response(invitation):
    """Notify the editor when a reviewer accepts or declines an invitation."""
    editor = invitation.invited_by
    if not editor.email:
        return

    status_text = "accepted" if invitation.status == "accepted" else "declined"
    subject = f'[Instructor: Journal of Computer Science and Applications] Invitation {status_text}: {invitation.article.title}'

    message = f"""
Dear {editor.get_full_name() or editor.username},

Reviewer {invitation.reviewer.get_full_name() or invitation.reviewer.username} has {status_text} your invitation to review the following article:

Title: {invitation.article.title}
Author: {invitation.article.author.get_full_name() or invitation.article.author.username}
Status: {status_text.capitalize()}

{f'You can view the article here: {settings.BASE_URL}{reverse("article_detail", args=[invitation.article.pk])}' if invitation.status == "accepted" else ''}

Best regards,
Instructor: Journal of Computer Science and Applications
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [editor.email])


def notify_editors_new_submission(article):
    """Notify all editors when an author submits an article for review."""
    editors = User.objects.filter(role='editor', is_active=True)
    editor_emails = [e.email for e in editors if e.email]
    
    if not editor_emails:
        return
    
    subject = f'[Instructor: Journal of Computer Science and Applications] New Submission: {article.title}'
    author_label = 'Anonymous' if article.is_anonymous else (article.author.get_full_name() or article.author.username)
    coauthors = article.co_authors.all()
    coauthor_info = ''
    if coauthors:
        coauthor_info = 'Co-Authors: ' + ', '.join([c.name for c in coauthors]) + '\n'
    ms = article.manuscript_number or 'N/A'
    
    message = f"""
A new article has been submitted for review.

Manuscript Number: {ms}
Title: {article.title}
Author: {author_label}
{coauthor_info}Abstract: {article.abstract[:200]}...
{'[This is an anonymous submission]' if article.is_anonymous else ''}

You can review it here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, editor_emails)


def notify_author_decision(article, decision):
    """Notify the author when an editor makes a decision on their article."""
    author = article.author
    if not author.email:
        return
    
    ms = article.manuscript_number or 'N/A'
    
    if decision == 'approved':
        subject = f'[Instructor: Journal of Computer Science and Applications] Article Approved: {article.title}'
        message = f"""
Congratulations! Your article has been approved for publication.

Manuscript Number: {ms}
Title: {article.title}
Status: Approved

Your article will be published soon. You can view it here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    elif decision == 'rejected':
        subject = f'[Instructor: Journal of Computer Science and Applications] Article Update: {article.title}'
        message = f"""
Your article has been reviewed, and unfortunately it has been rejected.

Manuscript Number: {ms}
Title: {article.title}
Status: Rejected

You can view the reviewer comments here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('article_detail', args=[article.pk])}
"""
    else:
        return
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [author.email])


def send_deadline_reminder(invitation, milestone):
    """Send a deadline reminder to the reviewer at a given milestone percentage."""
    reviewer = invitation.reviewer
    if not reviewer.email:
        return

    from django.template.defaultfilters import pluralize

    progress = invitation.deadline_progress()
    days_left = invitation.days_remaining()
    article_url = f'{settings.BASE_URL}{reverse("article_detail", args=[invitation.article.pk])}'
    submit_url = f'{settings.BASE_URL}{reverse("submit_review", args=[invitation.article.pk])}'

    if milestone == 50:
        reminder_text = (
            f"This is a friendly reminder that {progress:.0f}% of the review period has elapsed. "
            f"The editorial team is looking forward to your expert evaluation."
        )
    elif milestone == 75:
        reminder_text = (
            f"Three-quarters ({progress:.0f}%) of the review period is now complete. "
            f"Please make sure you are on track to submit your review on time."
        )
    elif milestone == 80:
        reminder_text = (
            f"{progress:.0f}% of the review period has elapsed. "
            f"We kindly remind you that your review is due soon."
        )
    elif milestone == 85:
        reminder_text = (
            f"{progress:.0f}% of the review period is complete. "
            f"The deadline is approaching — please finalize your review."
        )
    elif milestone == 90:
        reminder_text = (
            f"Only 10% of the review period remains ({progress:.0f}% elapsed)! "
            f"Please submit your review as soon as possible to meet the deadline."
        )
    elif milestone == 95:
        reminder_text = (
            f"Urgent: {progress:.0f}% of the review period has elapsed. "
            f"Only {days_left} day{pluralize(days_left)} remain{'' if days_left == 1 else ''} to submit your review."
        )
    elif milestone == 98:
        reminder_text = (
            f"Final reminder: {progress:.0f}% of the review period has elapsed. "
            f"Your review is due very soon. Please submit immediately to avoid delays."
        )
    else:
        reminder_text = (
            f"{progress:.0f}% of the review period has elapsed. "
            f"Please submit your review for '{invitation.article.title}'."
        )

    subject = f'[Instructor: Journal of Computer Science and Applications] Review Deadline Reminder: {invitation.article.title}'
    message = f"""
Dear {reviewer.get_full_name() or reviewer.username},

{reminder_text}

Article Details:
  Title: {invitation.article.title}
  Author: {invitation.article.author.get_full_name() or invitation.article.author.username}
  Review Deadline: {invitation.deadline.strftime("%B %d, %Y at %H:%M UTC") if invitation.deadline else "Not set"}
  Time Elapsed: {progress:.1f}%
  Days Remaining: {days_left if days_left else 0} day{pluralize(days_left or 0)}

Please submit your review here:
{submit_url}

You can also view the article here:
{article_url}

Thank you for your contribution to the peer review process.

Best regards,
Instructor: Journal of Computer Science and Applications
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [reviewer.email])
