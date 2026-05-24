from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from django.contrib.auth import get_user_model
from .models import Article, Review
from .forms import ArticleForm, ReviewForm
from .utils import notify_editors_new_submission, notify_author_decision

User = get_user_model()

# Existing views
@login_required
@user_passes_test(lambda u: u.is_author())
def create_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
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
    
    # Check if the current user (reviewer) has already submitted a review
    has_submitted_review = False
    if request.user.is_reviewer():
        user_review = Review.objects.filter(article=article, reviewer=request.user).first()
        if user_review and user_review.comments_to_author:
            has_submitted_review = True
    
    context = {
        'article': article,
        'reviews': reviews,
        'can_review': request.user.is_reviewer() and article.status == 'under_review' and not has_submitted_review
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
        notify_editors_new_submission(article)
        messages.success(request, 'Article submitted for review! Editors have been notified.')
    
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
    articles = Article.objects.all()
    reviews = Review.objects.filter(comments_to_author__isnull=False).exclude(comments_to_author='').order_by('-submitted_date')[:5]
    
    context = {
        'active': 'dashboard',
        'total_articles': articles.count(),
        'published_articles': articles.filter(status='published').count(),
        'pending_articles': articles.filter(status='submitted').count(),
        'under_review': articles.filter(status='under_review').count(),
        'total_users': User.objects.count(),
        'total_reviews': Review.objects.count(),
        'recent_articles': articles.order_by('-created_at')[:5],
        'recent_reviews': reviews,
    }
    return render(request, 'editor/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_articles(request):
    articles = Article.objects.all().order_by('-created_at')
    context = {
        'active': 'articles',
        'articles': articles,
    }
    return render(request, 'editor/articles.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_reviews(request):
    reviews = Review.objects.exclude(comments_to_author='').order_by('-submitted_date')
    context = {
        'active': 'reviews',
        'reviews': reviews,
    }
    return render(request, 'editor/reviews.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_pending(request):
    pending_articles = Article.objects.filter(status='submitted')
    under_review_articles = Article.objects.filter(status='under_review')
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
    
    if request.method == 'POST':
        reviewer_id = request.POST.get('reviewer_id')
        reviewer = get_object_or_404(User, pk=reviewer_id)
        
        Review.objects.create(
            article=article,
            reviewer=reviewer,
            comments_to_author="",
            comments_to_editor="",
            recommendation='major_revision'
        )
        
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

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_article_edit(request, pk):
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
    user_reviews = target_user.reviews.all()
    
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
# Ajouter ces fonctions à articles/views.py (à la fin du fichier)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_users(request):
    """Gérer tous les utilisateurs"""
    users = User.objects.all().order_by('-date_joined')
    
    # Statistiques
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
    """Voir les détails d'un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    user_articles = target_user.articles.all()
    user_reviews = target_user.reviews.all()
    
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
    """Modifier un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        target_user.username = request.POST.get('username')
        target_user.email = request.POST.get('email')
        target_user.role = request.POST.get('role')
        target_user.is_active = request.POST.get('is_active') == 'on'
        target_user.bio = request.POST.get('bio', '')
        target_user.save()
        
        messages.success(request, f'L\'utilisateur {target_user.username} a été mis à jour!')
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_delete(request, pk):
    """Supprimer un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    # Empêcher la suppression de soi-même
    if target_user == request.user:
        messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte!')
        return redirect('editor_users')
    
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'L\'utilisateur {username} a été supprimé!')
        return redirect('editor_users')
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_delete.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_toggle_status(request, pk):
    """Activer/Désactiver un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if target_user != request.user:
        target_user.is_active = not target_user.is_active
        target_user.save()
        status = "activé" if target_user.is_active else "désactivé"
        messages.success(request, f'L\'utilisateur {target_user.username} a été {status}!')
    else:
        messages.error(request, 'Vous ne pouvez pas modifier votre propre statut!')
    
    return redirect('editor_users')

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_change_role(request, pk):
    """Changer le rôle d'un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ['author', 'reviewer', 'editor']:
            old_role = target_user.role
            target_user.role = new_role
            target_user.save()
            messages.success(request, f'Rôle de {target_user.username} changé de {old_role} à {new_role}!')
        else:
            messages.error(request, 'Rôle invalide!')
        
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'target_user': target_user,
    }
    return render(request, 'editor/user_change_role.html', context)

# ========== GESTION DES UTILISATEURS ==========

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_users(request):
    """Gérer tous les utilisateurs"""
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
    """Voir les détails d'un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    user_articles = target_user.articles.all()
    user_reviews = target_user.reviews.all()
    
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
    """Modifier un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        target_user.username = request.POST.get('username')
        target_user.email = request.POST.get('email')
        target_user.role = request.POST.get('role')
        target_user.is_active = request.POST.get('is_active') == 'on'
        target_user.bio = request.POST.get('bio', '')
        target_user.save()
        
        messages.success(request, f'L\'utilisateur {target_user.username} a été mis à jour!')
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_edit.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_delete(request, pk):
    """Supprimer un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if target_user == request.user:
        messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte!')
        return redirect('editor_users')
    
    if request.method == 'POST':
        username = target_user.username
        target_user.delete()
        messages.success(request, f'L\'utilisateur {username} a été supprimé!')
        return redirect('editor_users')
    
    context = {
        'active': 'users',
        'target_user': target_user,
    }
    return render(request, 'editor/user_delete.html', context)

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_toggle_status(request, pk):
    """Activer/Désactiver un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if target_user != request.user:
        target_user.is_active = not target_user.is_active
        target_user.save()
        status = "activé" if target_user.is_active else "désactivé"
        messages.success(request, f'L\'utilisateur {target_user.username} a été {status}!')
    else:
        messages.error(request, 'Vous ne pouvez pas modifier votre propre statut!')
    
    return redirect('editor_users')

@login_required
@user_passes_test(lambda u: u.is_editor())
def editor_user_change_role(request, pk):
    """Changer le rôle d'un utilisateur"""
    target_user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ['author', 'reviewer', 'editor']:
            old_role = target_user.role
            target_user.role = new_role
            target_user.save()
            messages.success(request, f'Rôle de {target_user.username} changé de {old_role} à {new_role}!')
        else:
            messages.error(request, 'Rôle invalide!')
        
        return redirect('editor_user_detail', pk=target_user.pk)
    
    context = {
        'target_user': target_user,
    }
    return render(request, 'editor/user_change_role.html', context)
# Ajouter en haut du fichier avec les autres imports
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
import os

@login_required
def download_article_pdf(request, pk):
    """Télécharger un article au format PDF"""
    article = get_object_or_404(Article, pk=pk)
    
    # Vérifier les permissions
    can_view = False
    if request.user == article.author:
        can_view = True
    elif request.user.is_editor():
        can_view = True
    elif request.user.is_reviewer():
        if Review.objects.filter(article=article, reviewer=request.user).exists():
            can_view = True
    
    if not can_view:
        messages.error(request, 'Vous n\'avez pas la permission de télécharger cet article.')
        return redirect('dashboard')
    
    # Préparer le contexte pour le template PDF
    context = {
        'article': article,
        'user': request.user,
        'date': timezone.now(),
    }
    
    # Rendre le template HTML
    template = get_template('articles/article_pdf.html')
    html = template.render(context)
    
    # Créer la réponse PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="article_{article.id}_{article.title}.pdf"'
    
    # Générer le PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Erreur lors de la génération du PDF', status=500)
    
    return response
# Version alternative avec ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO

@login_required
def download_article_pdf_simple(request, pk):
    """Télécharger un article au format PDF (version simple)"""
    article = get_object_or_404(Article, pk=pk)
    
    # Créer un buffer pour le PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    
    # Créer un style personnalisé pour le titre
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#667eea'), alignment=1)
    
    # Contenu du PDF
    story = []
    
    # Titre principal
    story.append(Paragraph("Journal Platform", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Titre de l'article
    story.append(Paragraph(article.title, styles['Heading1']))
    story.append(Spacer(1, 0.5*cm))
    
    # Métadonnées
    story.append(Paragraph(f"Auteur: {article.author.username}", styles['Normal']))
    story.append(Paragraph(f"Statut: {article.get_status_display()}", styles['Normal']))
    story.append(Paragraph(f"Soumis le: {article.submitted_date.strftime('%d/%m/%Y') if article.submitted_date else 'Non soumis'}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Résumé
    story.append(Paragraph("Résumé", styles['Heading2']))
    story.append(Paragraph(article.abstract, styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Contenu
    story.append(Paragraph("Contenu", styles['Heading2']))
    story.append(Paragraph(article.content.replace('\n', '<br/>'), styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Mots-clés
    if article.keywords:
        story.append(Paragraph(f"Mots-clés: {article.keywords}", styles['Normal']))
    
    # Générer le PDF
    doc.build(story)
    
    # Retourner le PDF
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="article_{article.id}.pdf"'
    return response
