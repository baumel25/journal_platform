from django.db import models
from django.conf import settings
from django.utils import timezone

class Article(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('needs_revision', 'Needs Revision'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
    )
    
    title = models.CharField(max_length=200)
    abstract = models.TextField()
    content = models.TextField()
    keywords = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to='article_files/', blank=True, null=True, help_text='Upload your document (PDF, DOC, DOCX)')
    
    # Relationships
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='articles')
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_articles')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Dates
    submitted_date = models.DateTimeField(null=True, blank=True)
    under_review_date = models.DateTimeField(null=True, blank=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    published_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    def submit_for_review(self):
        self.status = 'submitted'
        self.submitted_date = timezone.now()
        self.save()
    
    def assign_to_reviewer(self):
        self.status = 'under_review'
        self.under_review_date = timezone.now()
        self.save()
    
    def approve(self):
        self.status = 'approved'
        self.approved_date = timezone.now()
        self.save()
    
    def publish(self):
        self.status = 'published'
        self.published_date = timezone.now()
        self.save()

class Review(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    
    # Review criteria
    originality_score = models.IntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    significance_score = models.IntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    methodology_score = models.IntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    clarity_score = models.IntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    
    comments_to_author = models.TextField()
    comments_to_editor = models.TextField(blank=True)
    
    recommendation = models.CharField(max_length=20, choices=(
        ('accept', 'Accept'),
        ('minor_revision', 'Minor Revision'),
        ('major_revision', 'Major Revision'),
        ('reject', 'Reject'),
    ))
    
    submitted_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Review of {self.article.title} by {self.reviewer.username}"
    
    def get_average_score(self):
        scores = [self.originality_score, self.significance_score, 
                 self.methodology_score, self.clarity_score]
        valid_scores = [s for s in scores if s is not None]
        if valid_scores:
            return sum(valid_scores) / len(valid_scores)
        return None