from django import forms
from .models import Article, Review

class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'abstract', 'content', 'keywords', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter article title'}),
            'abstract': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Write a brief abstract'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 15, 'placeholder': 'Write your article content here'}),
            'keywords': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., python, django, web development'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['originality_score', 'significance_score', 'methodology_score', 
                 'clarity_score', 'comments_to_author', 'comments_to_editor', 'recommendation']
        widgets = {
            'originality_score': forms.Select(attrs={'class': 'form-control'}, choices=[(i, i) for i in range(1, 6)]),
            'significance_score': forms.Select(attrs={'class': 'form-control'}, choices=[(i, i) for i in range(1, 6)]),
            'methodology_score': forms.Select(attrs={'class': 'form-control'}, choices=[(i, i) for i in range(1, 6)]),
            'clarity_score': forms.Select(attrs={'class': 'form-control'}, choices=[(i, i) for i in range(1, 6)]),
            'comments_to_author': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Provide constructive feedback to the author'}),
            'comments_to_editor': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Confidential comments for the editor'}),
            'recommendation': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('accept', 'Accept'),
                ('minor_revision', 'Minor Revision'),
                ('major_revision', 'Major Revision'),
                ('reject', 'Reject'),
            ]),
        }