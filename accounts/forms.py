from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.files.base import ContentFile
from .models import CustomUser
from PIL import Image
from io import BytesIO

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=[('author', 'Author'), ('reviewer', 'Reviewer')])
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'role', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'bio', 'profile_picture', 'whatsapp']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about yourself...'}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '+2250123456789'}),
        }
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            if picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File is too large (max 5MB)')
        return picture

    def save(self, commit=True):
        user = super().save(commit=False)
        picture = self.cleaned_data.get('profile_picture')
        
        if picture and hasattr(picture, 'read'):
            try:
                img = Image.open(picture)
                # Convert to RGB if needed (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize to max 300px on longest side (preserve aspect ratio)
                max_size = 300
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.LANCZOS)
                
                # Compress as JPEG quality 80
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=80, optimize=True)
                buffer.seek(0)
                
                # Change extension to .jpg
                filename = picture.name.rsplit('.', 1)[0] + '.jpg'
                user.profile_picture.save(filename, ContentFile(buffer.read()), save=False)
                
            except Exception:
                # On error, keep original image
                pass
        
        if commit:
            user.save()
            self.save_m2m()
        return user
