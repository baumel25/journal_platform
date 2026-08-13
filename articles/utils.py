import re
from html import escape

from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


def _send_mail_safe(subject, message, from_email, recipient_list):
    """Send email without crashing the request if SMTP fails (e.g. no
    EMAIL_HOST_PASSWORD configured yet)."""
    try:
        send_mail(subject, message, from_email, recipient_list)
    except Exception:
        pass


# Section headings commonly found in academic papers. Matching is case-insensitive
# and tolerates optional numbering (e.g. "1. Introduction" or "3.2 Methods").
_SECTION_HEADING_RE = re.compile(
    r'^(?:\d+(?:\.\d+)?[.)]\s*)?('
    r'abstract|introduction|background|literature\s+review|related\s+work|'
    r'methodology|methods?|materials?\s+and\s+methods|experimental\s+(?:setup|design|procedure)|'
    r'results?|findings|discussion|conclusion(?:s)?|'
    r'acknowledg(?:e)?ments?|references?|appendix(?:es)?|'
    r'funding|data\s+availability|conflict\s+of\s+interest|declarations?|'
    r'abbreviations?|author\s+contributions?'
    r')\s*:?\s*$',
    re.IGNORECASE,
)


def parse_article_blocks(content):
    """
    Split an article's plain-text body into a list of blocks that can be rendered
    in a journal layout. Returns a list of dicts:

        {'type': 'heading',   'number': 1, 'text': 'Introduction'}
        {'type': 'paragraph', 'number': None, 'text': '...'}

    A paragraph is treated as a section heading when it is a single short line
    that matches a known section name, or starts with an uppercase letter and
    does not end in sentence punctuation. Text is HTML-escaped (callers should
    render it with ``|safe``).
    """
    blocks = []
    section_num = 0

    paragraphs = re.split(r'\n\s*\n', content.strip())
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        lines = para.splitlines()
        single_line = len(lines) == 1
        short = len(para) <= 80
        no_end_punct = not para.endswith(('.', '!', '?', ':', ';', ','))

        is_heading = (
            single_line and short and no_end_punct
            and (_SECTION_HEADING_RE.match(para) or para[0].isupper())
        )

        if is_heading:
            section_num += 1
            blocks.append({'type': 'heading', 'number': section_num, 'text': escape(para)})
        else:
            # Join single newlines into <br/> so paragraphs keep their line breaks.
            escaped = escape('<br/>'.join(line.strip() for line in lines if line.strip()))
            blocks.append({'type': 'paragraph', 'number': None, 'text': escaped})

    return blocks


def notify_reviewer_invitation(invitation):
    """Send an email to the reviewer notifying them of a review invitation."""
    reviewer = invitation.reviewer
    if not reviewer.email:
        return

    subject = f'[Instructor: Journal of Computer Science and Applications] Review Invitation: {invitation.article.title}'
    accept_url = f'{settings.BASE_URL}{reverse("accept_invitation", args=[invitation.pk])}'
    decline_url = f'{settings.BASE_URL}{reverse("decline_invitation", args=[invitation.pk])}'
    dashboard_url = f'{settings.BASE_URL}{reverse("dashboard")}'

    # Always hide the author identity from reviewers in the invitation
    message = f"""
Dear {reviewer.get_full_name() or reviewer.username},

You have been invited by editor {invitation.invited_by.get_full_name() or invitation.invited_by.username} to review the following article:

Title: {invitation.article.title}
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
    _send_mail_safe(subject, message, settings.DEFAULT_FROM_EMAIL, [reviewer.email])


def notify_editor_invitation_response(invitation):
    """Notify the editor when a reviewer accepts or declines an invitation."""
    editor = invitation.invited_by
    if not editor.email:
        return

    status_text = "accepted" if invitation.status == "accepted" else "declined"
    subject = f'[Instructor: Journal of Computer Science and Applications] Invitation {status_text}: {invitation.article.title}'

    # Hide author identity if article is submitted anonymously
    author_label = 'Anonymous' if invitation.article.is_anonymous else (invitation.article.author.get_full_name() or invitation.article.author.username)

    message = f"""
Dear {editor.get_full_name() or editor.username},

Reviewer {invitation.reviewer.get_full_name() or invitation.reviewer.username} has {status_text} your invitation to review the following article:

Title: {invitation.article.title}
Author: {author_label}
Status: {status_text.capitalize()}

{f'You can view the article here: {settings.BASE_URL}{reverse("article_detail", args=[invitation.article.pk])}' if invitation.status == "accepted" else ''}

Best regards,
Instructor: Journal of Computer Science and Applications
"""
    _send_mail_safe(subject, message, settings.DEFAULT_FROM_EMAIL, [editor.email])


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
    _send_mail_safe(subject, message, settings.DEFAULT_FROM_EMAIL, editor_emails)


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
    elif decision == 'published':
        subject = f'[Instructor: Journal of Computer Science and Applications] Article Published: {article.title}'
        published_on = article.published_date.strftime('%B %d, %Y') if article.published_date else 'Today'
        message = f"""
Congratulations! Your article has been published in the journal.

Manuscript Number: {ms}
Title: {article.title}
Status: Published
Published on: {published_on}

You can now download your published article (journal format) here:
{settings.BASE_URL or 'http://localhost:8000'}{reverse('download_article_pdf', args=[article.pk])}
"""
    else:
        return
    
    _send_mail_safe(subject, message, settings.DEFAULT_FROM_EMAIL, [author.email])


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
    _send_mail_safe(subject, message, settings.DEFAULT_FROM_EMAIL, [reviewer.email])
