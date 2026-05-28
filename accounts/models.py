from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('author', 'Author'),
        ('reviewer', 'Reviewer'),
        ('editor', 'Editor'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='author')
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True, help_text='WhatsApp number with country code, e.g. +2250123456789')
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    
    def is_editor(self):
        return self.role == 'editor'
    
    def is_reviewer(self):
        return self.role == 'reviewer'
    
    def is_author(self):
        return self.role == 'author'
    
    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return '/static/defaults/default-avatar.png'
