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
    is_anonymous = models.BooleanField(default=False, help_text='Hide the author name from reviewers')
    manuscript_number = models.CharField(max_length=30, unique=True, blank=True, null=True, help_text='Auto-generated manuscript identifier (format: InstructorJCSA-XXXX)')
    
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
    
    def generate_manuscript_number(self):
        """Generate the next sequential manuscript number: InstructorJCSA-XXXX."""
        from django.db.models import Max
        prefix = 'InstructorJCSA-'
        # Find the highest existing order number
        last = Article.objects.filter(
            manuscript_number__startswith=prefix
        ).aggregate(Max('manuscript_number'))['manuscript_number__max']
        
        if last:
            last_num = int(last.split('-')[1])
            next_num = last_num + 1
        else:
            next_num = 1
        
        return f"{prefix}{next_num:04d}"

    def submit_for_review(self):
        if not self.manuscript_number:
            self.manuscript_number = self.generate_manuscript_number()
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

class CoAuthor(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='co_authors')
    name = models.CharField(max_length=200, verbose_name='Full Name')
    email = models.EmailField(verbose_name='Email Address')
    affiliation = models.CharField(max_length=300, blank=True, verbose_name='Institution / Affiliation')
    orcid = models.CharField(max_length=50, blank=True, verbose_name='ORCID iD')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'Co-Author'
        verbose_name_plural = 'Co-Authors'

    def __str__(self):
        return self.name


class ReviewInvitation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )

    ACCESS_CHOICES = (
        ('abstract_only', 'Abstract Only'),
        ('full', 'Full Article'),
    )

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='invitations')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='review_invitations')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_invitations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    access_level = models.CharField(max_length=20, choices=ACCESS_CHOICES, default='full', help_text='What parts of the article the reviewer can see')
    message = models.TextField(blank=True, help_text='Optional message from the editor to the reviewer')
    deadline_days = models.IntegerField(default=30, help_text='Number of days given to complete the review')
    deadline = models.DateTimeField(null=True, blank=True, help_text='Calculated deadline (set when invitation is accepted)')
    milestones_notified = models.JSONField(default=dict, blank=True, help_text='Tracks which percentage milestones have been notified')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invitation for {self.reviewer.username} to review '{self.article.title}' ({self.status})"

    def deadline_progress(self):
        """Return the percentage of time elapsed toward the deadline (0-100)."""
        if not self.deadline or not self.responded_at:
            return 0
        from django.utils import timezone
        total = self.deadline - self.responded_at
        if total.total_seconds() <= 0:
            return 100
        elapsed = timezone.now() - self.responded_at
        pct = (elapsed.total_seconds() / total.total_seconds()) * 100
        return min(round(pct, 1), 100)

    def days_remaining(self):
        """Return the number of days remaining until the deadline."""
        if not self.deadline:
            return None
        from django.utils import timezone
        remaining = self.deadline - timezone.now()
        return max(remaining.days, 0)

    def is_overdue(self):
        """Check if the deadline has passed."""
        if not self.deadline:
            return False
        from django.utils import timezone
        return timezone.now() > self.deadline


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

    # Editor approval: null=pending, True=approved, False=rejected
    editor_approved = models.BooleanField(null=True, blank=True, help_text='Null=pending editor review, True=approved, False=rejected')
    editor_reviewed_date = models.DateTimeField(null=True, blank=True)
    
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
    
    def is_pending_approval(self):
        """Check if the review is submitted but awaiting editor approval."""
        return bool(self.comments_to_author) and self.editor_approved is None
    
    def is_author_visible(self):
        """Check if this review should be visible to the author."""
        return self.editor_approved is True