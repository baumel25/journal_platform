from django.urls import path
from . import views

urlpatterns = [
    path('download-pdf/<int:pk>/', views.download_article_pdf, name='download_article_pdf'),
    # Author URLs
    path('create/', views.create_article, name='create_article'),
    path('<int:pk>/', views.article_detail, name='article_detail'),
    path('<int:pk>/edit/', views.edit_article, name='edit_article'),
    path('<int:pk>/submit/', views.submit_article, name='submit_article'),
    path('<int:pk>/review/', views.submit_review, name='submit_review'),
    path('<int:pk>/approve/', views.approve_article, name='approve_article'),
    path('<int:pk>/reject/', views.reject_article, name='reject_article'),
    path('my-articles/', views.my_articles, name='my_articles'),
    path('pending-reviews/', views.pending_reviews, name='pending_reviews'),
    
    # Editor URLs
    path('editor/dashboard/', views.editor_dashboard, name='editor_dashboard'),
    path('editor/articles/', views.editor_articles, name='editor_articles'),
    path('editor/reviews/', views.editor_reviews, name='editor_reviews'),
    path('editor/pending/', views.editor_pending, name='editor_pending'),
    path('editor/assign-reviewer/<int:pk>/', views.assign_reviewer, name='assign_reviewer'),
    path('editor/article/<int:pk>/edit/', views.editor_article_edit, name='editor_article_edit'),
    path('editor/article/<int:pk>/delete/', views.editor_article_delete, name='editor_article_delete'),
    
    # User Management URLs
    path('editor/users/', views.editor_users, name='editor_users'),
    path('editor/users/<int:pk>/', views.editor_user_detail, name='editor_user_detail'),
    path('editor/users/<int:pk>/edit/', views.editor_user_edit, name='editor_user_edit'),
    path('editor/users/<int:pk>/delete/', views.editor_user_delete, name='editor_user_delete'),
    path('editor/users/<int:pk>/toggle-status/', views.editor_user_toggle_status, name='editor_user_toggle_status'),
    path('editor/users/<int:pk>/change-role/', views.editor_user_change_role, name='editor_user_change_role'),
]

