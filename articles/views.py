import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Article, Review, ReviewInvitation, CoAuthor, ArticlePurchase
from .forms import ArticleForm, ReviewForm, CoAuthorFormSet
from .utils import notify_editors_new_submission, notify_author_decision, notify_reviewer_invitation, notify_editor_invitation_response
from .momo import MomoClient, MomoError, MomoNotConfigured, is_gateway_configured
from .journal_pdf import (
    generate_journal_pdf,
    generate_cover_pdf,
    generate_toc_pdf,
    generate_editorial_board_pdf,
)

User = get_user_model()

logger = logging.getLogger(__name__)

# Existing views
@login_required
@user_passes_test(lambda u: u.is_author())
def create_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        formset = CoAuthorFormSet(request.POST)
        
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.status = 'draft'
            article.save()
            
            if formset.is_valid():
                formset.instance = article
                formset.save()
            
            messages.success(request, 'Article created successfully!')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm()
        formset = CoAuthorFormSet()
    
    return render(request, 'articles/create_article.html', {'form': form, 'formset': formset})

def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    user = request.user
    is_authenticated = user.is_authenticated
    is_author_viewing = is_authenticated and (user == article.author)

    # Published articles are public (preview) so search engines and any visitor
    # can read the title + abstract. The full article is unlocked for the
    # author/editor/reviewer (full access) or after the reader has paid.
    # Non-published articles require login + permission.
    can_view = False
    can_view_full = False
    access_level = 'full'
    has_paid = False
    if article.status == 'published':
        can_view = True
        can_view_full = is_author_viewing or (is_authenticated and user.is_editor())
        if is_authenticated and user.is_reviewer():
            invitation = ReviewInvitation.objects.filter(
                article=article,
                reviewer=user,
                status='accepted',
            ).first()
            if invitation and invitation.access_level == 'full':
                can_view_full = True
            elif invitation:
                access_level = invitation.access_level
        if is_authenticated and not can_view_full:
            has_paid = ArticlePurchase.objects.filter(
                article=article, user=user, status='paid',
            ).exists()
            can_view_full = has_paid
    elif not is_authenticated:
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')
    elif is_author_viewing:
        can_view = True
        can_view_full = True
    elif user.is_editor():
        can_view = True
        can_view_full = True
    elif user.is_reviewer():
        # Reviewer can only view if they have accepted an invitation for this article
        invitation = ReviewInvitation.objects.filter(
            article=article,
            reviewer=user,
            status='accepted',
        ).first()
        if invitation:
            can_view = True
            can_view_full = invitation.access_level == 'full'
            access_level = invitation.access_level

    if not can_view:
        messages.error(request, 'You do not have permission to view this article.')
        return redirect('dashboard')

    # Reviews are only shown to logged-in users (with their role's visibility)
    reviews = []
    has_submitted_review = False
    if is_authenticated:
        if is_author_viewing:
            # Author only sees editor-approved reviews (anonymized)
            reviews = article.reviews.filter(editor_approved=True).select_related('reviewer')
            anonymous_reviews = []
            for review in reviews:
                anonymous_reviews.append({
                    'originality_score': review.originality_score,
                    'significance_score': review.significance_score,
                    'methodology_score': review.methodology_score,
                    'clarity_score': review.clarity_score,
                    'comments_to_author': review.comments_to_author,
                    'recommendation': review.recommendation,
                    'submitted_date': review.submitted_date,
                    'is_anonymous': True,
                })
            reviews = anonymous_reviews
        elif user.is_editor():
            # Editor sees all reviews (including pending approval)
            reviews = article.reviews.select_related('reviewer').all()
        else:
            # Reviewer sees only their own submitted reviews
            reviews = article.reviews.filter(reviewer=user).select_related('reviewer')

        # Check if the current user (reviewer) has already submitted a review
        if user.is_reviewer():
            user_review = Review.objects.filter(article=article, reviewer=user).first()
            if user_review and user_review.comments_to_author:
                has_submitted_review = True

    # Co-author visibility: editors and the article author can see them, reviewers cannot
    can_see_coauthors = is_author_viewing or (is_authenticated and user.is_editor())
    co_authors = article.co_authors.all() if can_see_coauthors else []

    context = {
        'article': article,
        'reviews': reviews,
        'co_authors': co_authors,
        'can_see_coauthors': can_see_coauthors,
        'access_level': access_level,
        'is_author_viewing': is_author_viewing,
        'can_view_full': can_view_full,
        'has_paid': has_paid,
        'is_public_view': article.status == 'published' and not is_authenticated,
        'is_preview': article.status == 'published' and not can_view_full,
        'can_review': is_authenticated and user.is_reviewer() and article.status == 'under_review' and not has_submitted_review,
    }
    return render(request, 'articles/article_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_author())
def edit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    
    if article.status not in ['draft', 'needs_revision']:
        messages.error(request, 'Cannot edit article after submission.')
        return redirect('article_detail', pk=article.pk)
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        formset = CoAuthorFormSet(request.POST, instance=article)
        
        if form.is_valid():
            article = form.save()
            if formset.is_valid():
                formset.save()
            messages.success(request, 'Article updated successfully!')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm(instance=article)
        formset = CoAuthorFormSet(instance=article)
    
    return render(request, 'articles/edit_article.html', {
        'form': form, 'formset': formset, 'article': article,
    })

@login_required
@user_passes_test(lambda u: u.is_author())
def submit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    
    if article.status != 'draft':
        messages.error(request, 'Article has already been submitted.')
    else:
        article.submit_for_review()
        notify_editors_new_submission(article)
        ms = article.manuscript_number or 'N/A'
        messages.success(
            request,
            f'Your article has been submitted successfully! '
            f'Your manuscript number is <strong>{ms}</strong>. '
            f'Please reference this number in all correspondence.'
        )
    
    return redirect('article_detail', pk=article.pk)

@login_required
@user_passes_test(lambda u: u.is_reviewer())
def submit_review(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    existing_review = Review.objects.filter(article=article, reviewer=request.user).first()
    
    if existing_review and existing_review.comments_to_author:
        messages.error(request, 'You have already submitted a review for this article.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            if existing_review:
                review = existing_review
                review.originality_score = form.cleaned_data['originality_score']
                review.significance_score = form.cleaned_data['significance_score']
                review.methodology_score = form.cleaned_data['methodology_score']
                review.clarity_score = form.cleaned_data['clarity_score']
                review.comments_to_author = form.cleaned_data['comments_to_author']
                review.comments_to_editor = form.cleaned_data['comments_to_editor']
                review.recommendation = form.cleaned_data['recommendation']
                review.save()
            else:
                review = form.save(commit=False)
                review.article = article
                review.reviewer = request.user
                review.save()
            
            messages.success(request, 'Your review has been submitted successfully!')
            return redirect('dashboard')
    else:
        if existing_review:
            form = ReviewForm(instance=existing_review)
        else:
            form = ReviewForm()
    
    context = {
        'form': form,
        'article': article,
        'existing_review': existing_review,
    }
    return render(request, 'articles/submit_review.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def approve_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    article.approve()
    notify_author_decision(article, 'approved')
    messages.success(request, f'Article "{article.title}" has been approved! Author has been notified.')
    return redirect('article_detail', pk=article.pk)

@login_required
@user_passes_test(lambda u: u.is_editor())
def reject_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    article.status = 'rejected'
    article.save()
    notify_author_decision(article, 'rejected')
    messages.warning(request, f'Article "{article.title}" has been rejected. Author has been notified.')
    return redirect('article_detail', pk=article.pk)

@login_required
@user_passes_test(lambda u: u.is_editor())
def publish_article(request, pk):
    """Publish a fully approved article. Only editors can do this."""
    article = get_object_or_404(Article, pk=pk)
    if article.status != 'approved':
        messages.error(request, 'Only fully approved articles can be published.')
        return redirect('article_detail', pk=article.pk)
    article.editor = request.user
    article.publish()
    notify_author_decision(article, 'published')
    messages.success(request, f'Article "{article.title}" has been published! The author can now download it online.')
    return redirect('article_detail', pk=article.pk)

@login_required
def my_articles(request):
    if not request.user.is_author():
        messages.error(request, 'Only authors can access this page.')
        return redirect('dashboard')
    
    articles = request.user.articles.all().order_by('-created_at')
    return render(request, 'articles/my_articles.html', {'articles': articles})

@login_required
def pending_reviews(request):
    if not request.user.is_reviewer():
        messages.error(request, 'Only reviewers can access this page.')
        return redirect('dashboard')
    
    reviews = Review.objects.filter(reviewer=request.user, article__status='under_review')
    return render(request, 'articles/pending_reviews.html', {'reviews': reviews})


# ─── Review Invitation Views ───────────────────────────────────────────

@login_required
def my_invitations(request):
    """Show pending review invitations for the reviewer."""
    if not request.user.is_reviewer():
        messages.error(request, 'Only reviewers can access invitations.')
        return redirect('dashboard')
    
    pending_invitations = ReviewInvitation.objects.filter(
        reviewer=request.user,
        status='pending',
    ).select_related('article', 'invited_by').order_by('-created_at')
    
    responded_invitations = ReviewInvitation.objects.filter(
        reviewer=request.user,
    ).exclude(status='pending').select_related('article', 'invited_by').order_by('-responded_at')
    
    context = {
        'pending_invitations': pending_invitations,
        'responded_invitations': responded_invitations,
    }
    return render(request, 'articles/my_invitations.html', context)


@login_required
def accept_invitation(request, pk):
    """Accept a review invitation."""
    if not request.user.is_reviewer():
        messages.error(request, 'Only reviewers can accept invitations.')
        return redirect('dashboard')
    
    invitation = get_object_or_404(ReviewInvitation, pk=pk, reviewer=request.user)
    
    if invitation.status != 'pending':
        messages.error(request, 'This invitation has already been responded to.')
        return redirect('my_invitations')
    
    # Create the Review object
    Review.objects.get_or_create(
        article=invitation.article,
        reviewer=request.user,
        defaults={
            'comments_to_author': "",
            'comments_to_editor': "",
            'recommendation': 'major_revision',
        }
    )
    
    # Update invitation status
    invitation.status = 'accepted'
    invitation.responded_at = timezone.now()
    # Calculate deadline from acceptance date + deadline_days
    from datetime import timedelta
    invitation.deadline = timezone.now() + timedelta(days=invitation.deadline_days)
    invitation.save()
    
    # Update article status if this is the first accepted review
    if invitation.article.status == 'submitted':
        invitation.article.assign_to_reviewer()
    
    # Notify the editor
    notify_editor_invitation_response(invitation)
    
    messages.success(
        request,
        f'You have accepted the invitation to review "{invitation.article.title}". '
        f'You can now view and review the article.'
    )
    return redirect('article_detail', pk=invitation.article.pk)


@login_required
def decline_invitation(request, pk):
    """Decline a review invitation."""
    if not request.user.is_reviewer():
        messages.error(request, 'Only reviewers can decline invitations.')
        return redirect('dashboard')
    
    invitation = get_object_or_404(ReviewInvitation, pk=pk, reviewer=request.user)
    
    if invitation.status != 'pending':
        messages.error(request, 'This invitation has already been responded to.')
        return redirect('my_invitations')
    
    # Update invitation status
    invitation.status = 'declined'
    invitation.responded_at = timezone.now()
    invitation.save()
    
    # Notify the editor
    notify_editor_invitation_response(invitation)
    
    messages.info(
        request,
        f'You have declined the invitation to review "{invitation.article.title}". '
        f'The editor has been notified.'
    )
    return redirect('my_invitations')


# Editor Admin Views
@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_dashboard(request):
    articles = Article.objects.all()
    reviews = Review.objects.filter(comments_to_author__isnull=False).exclude(comments_to_author='').order_by('-submitted_date')[:5]
    
    pending_review_approvals = Review.objects.filter(
        comments_to_author__isnull=False,
    ).exclude(comments_to_author='').filter(
        editor_approved__isnull=True,
    ).count()
    
    context = {
        'active': 'dashboard',
        'total_articles': articles.count(),
        'published_articles': articles.filter(status='published').count(),
        'pending_articles': articles.filter(status='submitted').count(),
        'under_review': articles.filter(status='under_review').count(),
        'total_users': User.objects.count(),
        'total_reviews': Review.objects.count(),
        'pending_review_approvals': pending_review_approvals,
        'recent_articles': articles.order_by('-created_at')[:5],
        'recent_reviews': reviews,
    }
    return render(request, 'editor/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_articles(request):
    articles = Article.objects.select_related('author').all().order_by('-created_at')
    context = {
        'active': 'articles',
        'articles': articles,
    }
    return render(request, 'editor/articles.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_reviews(request):
    reviews = Review.objects.select_related('article', 'reviewer').exclude(comments_to_author='').order_by('-submitted_date')
    context = {
        'active': 'reviews',
        'reviews': reviews,
    }
    return render(request, 'editor/reviews.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_pending(request):
    pending_articles = Article.objects.select_related('author').filter(status='submitted')
    under_review_articles = Article.objects.select_related('author').filter(status='under_review')
    context = {
        'active': 'pending',
        'pending_articles': pending_articles,
        'under_review_articles': under_review_articles,
    }
    return render(request, 'editor/pending.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def assign_reviewer(request, pk):
    article = get_object_or_404(Article, pk=pk)
    reviewers = User.objects.filter(role='reviewer')
    
    # Exclude reviewers who already have a pending/accepted invitation for this article
    already_invited = ReviewInvitation.objects.filter(
        article=article, reviewer__in=reviewers
    ).values_list('reviewer_id', flat=True)
    reviewers = reviewers.exclude(id__in=already_invited)
    
    if request.method == 'POST':
        reviewer_id = request.POST.get('reviewer_id')
        message = request.POST.get('message', '')
        access_level = request.POST.get('access_level', 'full')
        if access_level not in ('abstract_only', 'full'):
            access_level = 'full'
        deadline_days = request.POST.get('deadline_days', 30)
        try:
            deadline_days = int(deadline_days)
            if deadline_days < 1:
                deadline_days = 30
        except (ValueError, TypeError):
            deadline_days = 30
        
        reviewer = get_object_or_404(User, pk=reviewer_id)
        
        # Create the invitation
        invitation = ReviewInvitation.objects.create(
            article=article,
            reviewer=reviewer,
            invited_by=request.user,
            message=message,
            access_level=access_level,
            deadline_days=deadline_days,
            status='pending',
        )
        
        # Send email notification to the reviewer
        notify_reviewer_invitation(invitation)
        
        messages.success(
            request,
            f'Review invitation sent to {reviewer.get_full_name() or reviewer.username} for "{article.title}". '
            f'They will be notified by email.'
        )
        return redirect('editor_pending')
    
    context = {
        'article': article,
        'reviewers': reviewers,
        'active': 'pending',
    }
    return render(request, 'editor/assign_reviewer.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_article_edit(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, 'Article updated successfully!')
            return redirect('editor_articles')
    else:
        form = ArticleForm(instance=article)
    
    context = {
        'form': form,
        'article': article,
        'active': 'articles',
    }
    return render(request, 'editor/article_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_article_delete(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    if request.method == 'POST':
        article.delete()
        messages.success(request, 'Article deleted successfully!')
        return redirect('editor_articles')
    
    context = {
        'article': article,
        'active': 'articles',
    }
    return render(request, 'editor/article_delete.html', context)

# ========== USER MANAGEMENT VIEWS ==========

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_users(request):
    """Manage all users"""
    users = User.objects.all().order_by('-date_joined')
    
    total_users = users.count()
    authors = users.filter(role='author').count()
    reviewers = users.filter(role='reviewer').count()
    editors = users.filter(role='editor').count()
    active_users = users.filter(is_active=True).count()
    
    context = {
        'active': 'users',
        'users': users,
        'total_users': total_users,
        'authors_count': authors,
        'reviewers_count': reviewers,
        'editors_count': editors,
        'active_count': active_users,
    }
    return render(request, 'editor/users.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_detail(request, pk):
    """View user details"""
    target_user = get_object_or_404(User, pk=pk)
    user_articles = target_user.articles.all()
    user_reviews = target_user.reviews.select_related('article').all()
    
    context = {
        'active': 'users',
        'target_user': target_user,
        'articles': user_articles,
        'reviews': user_reviews,
    }
    return render(request, 'editor/user_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_edit(request, pk):
    """Edit user information"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        target_user.username = request.POST.get('username')
        target_user.email = request.POST.get('email')
        target_user.role = request.POST.get('role')
        target_user.is_active = request.POST.get('is_active') == 'on'
        target_user.bio = request.POST.get('bio', '')
        
        target_user.save()
        messages.success(request, f'User {target_user.username} has been updated successfully!')
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_delete(request, pk):
    """Delete a user"""
    target_user = get_object_or_404(User, pk=pk)
    
    if target_user == request.user:
        messages.error(request, 'You cannot delete your own account!')
        return redirect('editor_users')
    
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'User {username} has been deleted successfully!')
        return redirect('editor_users')
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_delete.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_toggle_status(request, pk):
    """Activate or deactivate a user"""
    target_user = get_object_or_404(User, pk=pk)
    
    if target_user != request.user:
        target_user.is_active = not target_user.is_active
        target_user.save()
        status = "activated" if target_user.is_active else "deactivated"
        messages.success(request, f'User {target_user.username} has been {status}!')
    else:
        messages.error(request, 'You cannot change your own status!')
    
    return redirect('editor_users')

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_change_role(request, pk):
    """Change user role"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ['author', 'reviewer', 'editor']:
            old_role = target_user.role
            target_user.role = new_role
            target_user.save()
            messages.success(request, f'User {target_user.username}\'s role changed from {old_role} to {new_role}!')
        else:
            messages.error(request, 'Invalid role!')
        
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'target_user': target_user,
    }
    return render(request, 'editor/user_change_role.html', context)

# ========== REVIEW APPROVAL VIEWS ==========

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_pending_reviews(request):
    """List all submitted reviews pending editor approval."""
    pending_reviews = Review.objects.filter(
        comments_to_author__isnull=False,
    ).exclude(comments_to_author='').filter(
        editor_approved__isnull=True,
    ).select_related('article', 'reviewer', 'article__author').order_by('-submitted_date')
    
    context = {
        'active': 'reviews',
        'pending_reviews': pending_reviews,
        'approved_reviews': Review.objects.filter(editor_approved=True).select_related('article', 'reviewer').order_by('-editor_reviewed_date')[:10],
        'rejected_reviews': Review.objects.filter(editor_approved=False).select_related('article', 'reviewer').order_by('-editor_reviewed_date')[:10],
    }
    return render(request, 'editor/review_approvals.html', context)


@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_approve_review(request, pk):
    """Approve a review so the author can see it."""
    review = get_object_or_404(Review, pk=pk)
    
    if review.editor_approved is not None:
        messages.warning(request, 'This review has already been processed.')
        return redirect('editor_pending_reviews')
    
    review.editor_approved = True
    review.editor_reviewed_date = timezone.now()
    review.save()
    
    messages.success(
        request,
        f'Review of "{review.article.title}" by {review.reviewer.username} has been approved. '
        f'The author can now view it.'
    )
    return redirect('article_detail', pk=review.article.pk)


@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_reject_review(request, pk):
    """Reject a review so the author never sees it."""
    review = get_object_or_404(Review, pk=pk)
    
    if review.editor_approved is not None:
        messages.warning(request, 'This review has already been processed.')
        return redirect('editor_pending_reviews')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        review.editor_approved = False
        review.editor_reviewed_date = timezone.now()
        review.save()
        
        messages.info(
            request,
            f'Review of "{review.article.title}" by {review.reviewer.username} has been rejected. '
            f'It will not be shown to the author.'
        )
        return redirect('editor_pending_reviews')
    
    context = {
        'review': review,
        'active': 'reviews',
    }
    return render(request, 'editor/review_reject.html', context)


@login_required
def download_article_pdf(request, pk):
    """Download an article as PDF (ReportLab; no xhtml2pdf dependency)."""
    from django.http import HttpResponse
    from django.utils.text import slugify

    article = get_object_or_404(Article, pk=pk)
    user = request.user

    # Check permissions
    can_view = False
    if user.is_authenticated:
        if user == article.author:
            can_view = True
        elif user.is_editor():
            can_view = True
        elif user.is_reviewer():
            invitation = ReviewInvitation.objects.filter(
                article=article,
                reviewer=user,
                status='accepted',
            ).first()
            if invitation:
                if invitation.access_level == 'abstract_only':
                    messages.error(request, 'You only have abstract-only access. Full document download is not available.')
                    return redirect('article_detail', pk=article.pk)
                can_view = True
        # Paid readers can download the published journal PDF.
        if not can_view and article.status == 'published':
            can_view = ArticlePurchase.objects.filter(
                article=article, user=user, status='paid',
            ).exists()

    if not can_view:
        messages.error(request, 'You do not have permission to download this article.')
        return redirect('dashboard')

    # Published articles are produced in the standard journal layout.
    if article.status == 'published':
        pdf_bytes = generate_journal_pdf(article)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe_title = slugify(article.title) or f'article-{article.id}'
        response['Content-Disposition'] = f'attachment; filename="{safe_title}.pdf"'
        return response

    # Non-published articles: simple working version (journal format on publish only).
    return download_article_pdf_simple(request, pk)


# ═══════════════════════════════════════════════════════════════════════════
# Paid access to full published articles (MTN MoMo)
# ═══════════════════════════════════════════════════════════════════════════

def _validate_momo_number(phone):
    """Return True if the phone looks like a Cameroonian MoMo number (6XXXXXXXX)."""
    import re
    return bool(re.fullmatch(r'6\d{8}', str(phone).strip()))


@login_required
def pay_article(request, pk):
    """Payment page to unlock a full published article."""
    article = get_object_or_404(Article, pk=pk)
    if article.status != 'published':
        messages.error(request, 'Only published articles can be purchased.')
        return redirect('article_detail', pk=article.pk)

    already = ArticlePurchase.objects.filter(
        article=article, user=request.user, status='paid',
    ).exists()
    if already:
        messages.info(request, 'You already have full access to this article.')
        return redirect('article_detail', pk=article.pk)

    gateway_configured = is_gateway_configured()
    context = {
        'article': article,
        'gateway_configured': gateway_configured,
        'phone': request.POST.get('phone_number', ''),
    }

    if request.method == 'POST':
        phone = request.POST.get('phone_number', '').strip()
        if not _validate_momo_number(phone):
            messages.error(request, 'Please enter a valid MoMo number (format: 6XXXXXXXX).')
            context['phone'] = phone
            return render(request, 'articles/pay_article.html', context)

        purchase, _ = ArticlePurchase.objects.get_or_create(
            article=article,
            user=request.user,
            status='pending',
            defaults={'amount': article.price, 'phone_number': phone},
        )
        if not purchase.reference:
            purchase.reference = purchase.generate_reference()
        purchase.amount = article.price
        purchase.phone_number = phone
        purchase.status = 'pending'
        purchase.save()

        if gateway_configured:
            try:
                client = MomoClient()
                reference_id, _ = client.request_to_pay(
                    amount=article.price,
                    phone_number=phone,
                    external_id=purchase.reference,
                    payer_message=f'INSTRUCTOR JCSA - {article.title[:40]}',
                    payee_note='Full article access',
                )
                purchase.momo_transaction_id = reference_id
                purchase.save(update_fields=['momo_transaction_id'])
            except MomoError as exc:
                logger.error('MoMo request_to_pay failed for %s: %s', purchase.reference, exc)
                messages.error(
                    request,
                    'We could not start the mobile money request. Please try again '
                    'in a moment or contact the editorial office.'
                )
                return render(request, 'articles/pay_article.html', context)
        else:
            messages.info(
                request,
                'A payment request has been created. Complete your payment and the '
                'editorial office will confirm it shortly.'
            )

        return redirect('payment_status', pk=article.pk)

    return render(request, 'articles/pay_article.html', context)


@login_required
def payment_status(request, pk):
    """Show the status of the user's latest purchase attempt for an article."""
    article = get_object_or_404(Article, pk=pk)
    purchase = ArticlePurchase.objects.filter(
        article=article, user=request.user,
    ).order_by('-created_at').first()

    if not purchase:
        messages.info(request, 'No payment found for this article.')
        return redirect('pay_article', pk=article.pk)

    # If still pending and we have a MoMo transaction id, check the gateway so
    # the page reflects the true state even without the callback.
    if (purchase.status == 'pending' and purchase.momo_transaction_id
            and is_gateway_configured()):
        try:
            data = MomoClient().get_transaction_status(purchase.momo_transaction_id)
            momo_status = (data.get('status') or '').upper()
            if momo_status == 'SUCCESSFUL':
                purchase.mark_paid(data.get('financialTransactionId', ''))
            elif momo_status == 'FAILED':
                purchase.status = 'failed'
                purchase.save(update_fields=['status'])
        except MomoError:
            pass  # keep pending; the callback may still confirm it

    if not purchase.reference:
        purchase.reference = purchase.generate_reference()
        purchase.save(update_fields=['reference'])

    context = {
        'article': article,
        'purchase': purchase,
        'gateway_configured': is_gateway_configured(),
    }
    return render(request, 'articles/payment_status.html', context)


@csrf_exempt
@require_POST
def payment_callback(request):
    """Webhook called by MTN MoMo when a request-to-pay completes.

    The callback payload carries our internal reference in ``externalId`` and
    the transaction ``status`` (SUCCESSFUL/FAILED). We mark the matching
    purchase as paid so the reader gets full access.
    """
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        data = {}

    status = (data.get('status') or '').upper()
    external_id = data.get('externalId') or ''
    reference_id = request.headers.get('X-Reference-Id') or ''

    purchase = None
    if external_id:
        purchase = ArticlePurchase.objects.filter(reference=external_id).first()
    if purchase is None and reference_id:
        purchase = ArticlePurchase.objects.filter(momo_transaction_id=reference_id).first()

    if purchase and status == 'SUCCESSFUL':
        # Verify server-side with the MoMo API before granting access so a
        # forged callback cannot unlock an article without a real payment.
        if is_gateway_configured() and purchase.momo_transaction_id:
            try:
                verified = MomoClient().get_transaction_status(purchase.momo_transaction_id)
                if (verified.get('status') or '').upper() != 'SUCCESSFUL':
                    return HttpResponse('Verification failed', status=409)
            except MomoError:
                return HttpResponse('Verification unavailable', status=409)
        purchase.mark_paid(data.get('financialTransactionId', ''))
        return HttpResponse('OK')
    if purchase and status == 'FAILED':
        purchase.status = 'failed'
        purchase.save(update_fields=['status'])
        return HttpResponse('OK')

    logger.info('MoMo callback for unknown reference (externalId=%s, status=%s)', external_id, status)
    return HttpResponse('No matching payment', status=404)


@login_required
def my_purchases(request):
    """List the articles the current user has paid to unlock."""
    purchases = ArticlePurchase.objects.filter(
        user=request.user, status='paid',
    ).select_related('article').order_by('-paid_at')
    return render(request, 'articles/my_purchases.html', {'purchases': purchases})


@login_required
def download_article_file(request, pk):
    """Stream the uploaded article document, enforcing full-access permissions.

    Raw uploaded files under ``article_files/`` are NOT served publicly; they
    can only be downloaded through this view by the author, an editor, a
    reviewer with full access, or a reader who has paid to unlock the article.
    """
    from django.http import FileResponse, Http404

    article = get_object_or_404(Article, pk=pk)
    user = request.user
    if not article.file:
        raise Http404('No document uploaded for this article.')

    can_view = False
    if user == article.author:
        can_view = True
    elif user.is_editor():
        can_view = True
    elif user.is_reviewer():
        invitation = ReviewInvitation.objects.filter(
            article=article, reviewer=user, status='accepted',
        ).first()
        if invitation and invitation.access_level == 'full':
            can_view = True
    if not can_view and article.status == 'published':
        can_view = ArticlePurchase.objects.filter(
            article=article, user=user, status='paid',
        ).exists()

    if not can_view:
        messages.error(request, 'You do not have permission to download this document.')
        return redirect('article_detail', pk=article.pk)

    filename = article.file.name.split('/')[-1]
    response = FileResponse(article.file.open('rb'), as_attachment=True, filename=filename)
    return response
# Alternative version using ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO

@login_required
def download_article_pdf_simple(request, pk):
    """Download an article as PDF (simple version)"""
    article = get_object_or_404(Article, pk=pk)
    
    # Check permissions (respect access level)
    if request.user.is_reviewer():
        invitation = ReviewInvitation.objects.filter(
            article=article,
            reviewer=request.user,
            status='accepted',
        ).first()
        if invitation and invitation.access_level == 'abstract_only':
            messages.error(request, 'You only have abstract-only access. Full document download is not available.')
            return redirect('article_detail', pk=article.pk)
    
    # Create a buffer for the PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    # Create custom style for the title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#667eea'), alignment=1)
    
    # PDF content
    story = []
    
    # Main title
    story.append(Paragraph("Instructor: Journal of Computer Science and Applications", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Article title
    story.append(Paragraph(article.title, styles['Heading1']))
    story.append(Spacer(1, 0.5*cm))
    
    # Metadata
    story.append(Paragraph(f"Author: {article.author.username}", styles['Normal']))
    story.append(Paragraph(f"Status: {article.get_status_display()}", styles['Normal']))
    story.append(Paragraph(f"Submitted: {article.submitted_date.strftime('%d/%m/%Y') if article.submitted_date else 'Not submitted'}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Abstract
    story.append(Paragraph("Abstract", styles['Heading2']))
    story.append(Paragraph(article.abstract, styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Content
    story.append(Paragraph("Content", styles['Heading2']))
    story.append(Paragraph(article.content.replace('\n', '<br/>'), styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Keywords
    if article.keywords:
        story.append(Paragraph(f"Keywords: {article.keywords}", styles['Normal']))
    
    # Generate the PDF
    doc.build(story)
    
    # Return the PDF
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="article_{article.id}.pdf"'
    return response


def _pdf_preview_png(pdf_bytes):
    """Render the first page of a PDF to a base64-encoded PNG (best effort)."""
    try:
        import base64
        import pypdfium2 as pdfium
        from io import BytesIO

        pdf = pdfium.PdfDocument(pdf_bytes)
        try:
            page = pdf[0]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil().convert("RGB")
            buf = BytesIO()
            image.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        finally:
            pdf.close()
    except Exception:
        return None


@login_required
def journal_cover_preview(request):
    """Show a rendered preview of the journal cover, with a download button."""
    return render(request, 'articles/journal_cover.html', {
        'cover_png': _pdf_preview_png(generate_cover_pdf()),
    })


def journal_about(request):
    """Public 'About the Journal' page with scope and submission information."""
    return render(request, 'articles/journal_about.html')


def published_articles(request):
    """Public listing of published articles (preview: title + abstract only)."""
    articles = Article.objects.filter(status='published').order_by('-published_date')
    return render(request, 'articles/published_articles.html', {'articles': articles})


@login_required
def download_journal_cover(request):
    """Download the journal cover page (logo + journal title)."""
    pdf_bytes = generate_cover_pdf()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="journal-cover.pdf"'
    return response


@login_required
def journal_toc_preview(request):
    """Show a rendered preview of the journal table of contents."""
    articles = Article.objects.filter(status='published').order_by('published_date')
    return render(request, 'articles/journal_toc.html', {
        'toc_png': _pdf_preview_png(generate_toc_pdf(articles)),
    })


@login_required
def download_journal_toc(request):
    """Download the journal table of contents (published articles + page ranges)."""
    articles = Article.objects.filter(status='published').order_by('published_date')
    pdf_bytes = generate_toc_pdf(articles)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="journal-table-of-contents.pdf"'
    return response


@login_required
def editorial_board_preview(request):
    """Show a rendered preview of the journal editorial board."""
    return render(request, 'articles/editorial_board.html', {
        'board_png': _pdf_preview_png(generate_editorial_board_pdf()),
    })


@login_required
def download_editorial_board(request):
    """Download the journal editorial board page."""
    pdf_bytes = generate_editorial_board_pdf()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="journal-editorial-board.pdf"'
    return response
