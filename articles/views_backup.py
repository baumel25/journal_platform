from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from .models import Article, Review
from .forms import ArticleForm, ReviewForm

User = get_user_model()

# Existing views
@login_required
@user_passes_test(lambda u: u.is_author())
def create_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.status = 'draft'
            article.save()
            messages.success(request, 'Article created successfully!')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm()
    return render(request, 'articles/create_article.html', {'form': form})

@login_required
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    # Check permissions
    can_view = False
    if request.user == article.author:
        can_view = True
    elif request.user.is_editor():
        can_view = True
    elif request.user.is_reviewer():
        if Review.objects.filter(article=article, reviewer=request.user).exists():
            can_view = True
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this article.')
        return redirect('dashboard')
    
    reviews = article.reviews.all()
    context = {
        'article': article,
        'reviews': reviews,
        'can_review': request.user.is_reviewer() and article.status == 'under_review' 
                      and not Review.objects.filter(article=article, reviewer=request.user).exists()
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
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            messages.success(request, 'Article updated successfully!')
            return redirect('article_detail', pk=article.pk)
    else:
        form = ArticleForm(instance=article)
    return render(request, 'articles/edit_article.html', {'form': form, 'article': article})

@login_required
@user_passes_test(lambda u: u.is_author())
def submit_article(request, pk):
    article = get_object_or_404(Article, pk=pk, author=request.user)
    
    if article.status != 'draft':
        messages.error(request, 'Article has already been submitted.')
    else:
        article.submit_for_review()
        messages.success(request, 'Article submitted for review!')
    
    return redirect('article_detail', pk=article.pk)

@login_required
@user_passes_test(lambda u: u.is_reviewer())
def submit_review(request, pk):
    article = get_object_or_404(Article, pk=pk)
    
    # Check if review already exists
    if Review.objects.filter(article=article, reviewer=request.user).exists():
        messages.error(request, 'You have already reviewed this article.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.article = article
            review.reviewer = request.user
            review.save()
            messages.success(request, 'Review submitted successfully!')
            return redirect('dashboard')
    else:
        form = ReviewForm()
    
    return render(request, 'articles/submit_review.html', {'form': form, 'article': article})

@login_required
@user_passes_test(lambda u: u.is_editor())
def approve_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    article.approve()
    messages.success(request, f'Article "{article.title}" has been approved!')
    return redirect('article_detail', pk=article.pk)

@login_required
@user_passes_test(lambda u: u.is_editor())
def reject_article(request, pk):
    article = get_object_or_404(Article, pk=pk)
    article.status = 'rejected'
    article.save()
    messages.warning(request, f'Article "{article.title}" has been rejected.')
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

# Editor Admin Views
@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_dashboard(request):
    """Editor Admin Dashboard"""
    articles = Article.objects.all()
    
    context = {
        'active': 'dashboard',
        'total_articles': articles.count(),
        'published_articles': articles.filter(status='published').count(),
        'pending_articles': articles.filter(status='submitted').count(),
        'under_review': articles.filter(status='under_review').count(),
        'total_users': User.objects.count(),
        'total_reviews': Review.objects.count(),
        'recent_articles': articles.order_by('-created_at')[:5],
    }
    return render(request, 'editor/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_articles(request):
    """Manage all articles"""
    articles = Article.objects.all().order_by('-created_at')
    context = {
        'active': 'articles',
        'articles': articles,
    }
    return render(request, 'editor/articles.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_users(request):
    """Manage all users"""
    users = User.objects.all()
    context = {
        'active': 'users',
        'users': users,
    }
    return render(request, 'editor/users.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_reviews(request):
    """View all reviews"""
    reviews = Review.objects.all().order_by('-submitted_date')
    context = {
        'active': 'reviews',
        'reviews': reviews,
    }
    return render(request, 'editor/reviews.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_pending(request):
    """View pending articles for approval"""
    pending_articles = Article.objects.filter(status='submitted')
    context = {
        'active': 'pending',
        'articles': pending_articles,
    }
    return render(request, 'editor/pending.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_article_edit(request, pk):
    """Edit article as editor"""
    article = get_object_or_404(Article, pk=pk)
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=article)
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
    """Delete article"""
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

@login_required
@user_passes_test(lambda u: u.is_editor())
def assign_reviewer(request, pk):
    """Assign a reviewer to an article"""
    article = get_object_or_404(Article, pk=pk)
    reviewers = User.objects.filter(role='reviewer')
    
    if request.method == 'POST':
        reviewer_id = request.POST.get('reviewer_id')
        reviewer = get_object_or_404(User, pk=reviewer_id)
        
        # Create the review assignment
        Review.objects.create(
            article=article,
            reviewer=reviewer,
            comments_to_author="",
            comments_to_editor="",
            recommendation='major_revision'
        )
        
        # Update article status to under_review
        article.status = 'under_review'
        article.under_review_date = timezone.now()
        article.save()
        
        messages.success(request, f'Reviewer {reviewer.username} has been assigned to "{article.title}"')
        return redirect('editor_pending')
    
    context = {
        'article': article,
        'reviewers': reviewers,
        'active': 'pending',
    }
    return render(request, 'editor/assign_reviewer.html', context)
