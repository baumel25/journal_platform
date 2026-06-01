from django.contrib import admin
from .models import Article, Review, ReviewInvitation, CoAuthor

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'submitted_date', 'published_date']
    list_filter = ['status', 'author', 'submitted_date']
    search_fields = ['title', 'abstract']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['article', 'reviewer', 'recommendation', 'submitted_date']
    list_filter = ['recommendation', 'reviewer']

@admin.register(CoAuthor)
class CoAuthorAdmin(admin.ModelAdmin):
    list_display = ['name', 'article', 'email', 'affiliation']
    list_filter = ['affiliation']
    search_fields = ['name', 'email', 'article__title']


@admin.register(ReviewInvitation)
class ReviewInvitationAdmin(admin.ModelAdmin):
    list_display = ['article', 'reviewer', 'invited_by', 'status', 'created_at', 'responded_at']
    list_filter = ['status', 'reviewer', 'invited_by']
    search_fields = ['article__title', 'reviewer__username']