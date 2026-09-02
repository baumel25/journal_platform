from django.contrib import admin
from .models import Article, Review, ReviewInvitation, CoAuthor, ArticlePurchase

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


@admin.register(ArticlePurchase)
class ArticlePurchaseAdmin(admin.ModelAdmin):
    list_display = ['reference', 'article', 'user', 'amount', 'phone_number', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reference', 'article__title', 'user__username', 'phone_number', 'momo_transaction_id']
    readonly_fields = ['reference', 'created_at', 'paid_at']
    actions = ['mark_as_paid', 'mark_as_failed']

    def mark_as_paid(self, request, queryset):
        target = queryset.filter(status__in=['pending', 'failed'])
        count = target.count()
        for purchase in target:
            purchase.mark_paid()
        self.message_user(request, f'{count} purchase(s) marked as paid.')
    mark_as_paid.short_description = 'Mark selected purchases as PAID (manual confirmation)'

    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='failed')
        self.message_user(request, f'{updated} purchase(s) marked as failed.')
    mark_as_failed.short_description = 'Mark selected purchases as FAILED'