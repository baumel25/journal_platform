from django.contrib import admin
from .models import Article, Review

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