from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .forms import RegistrationForm, UserProfileForm
from .models import CustomUser

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'accounts/home.html')

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome {user.username}! You are registered as {user.get_role_display()}.')
            return redirect('dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back {username}!')
                return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    
    form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')

@login_required
def dashboard(request):
    from articles.models import Article
    
    context = {}
    
    if request.user.is_editor():
        return redirect('editor_dashboard')
    elif request.user.is_reviewer():
        context['reviews'] = request.user.reviews.all()
    elif request.user.is_author():
        context['my_articles'] = request.user.articles.all().order_by('-created_at')
    
    return render(request, 'accounts/dashboard.html', context)

@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})

@login_required
def delete_profile_picture(request):
    """Supprimer la photo de profil"""
    if request.user.profile_picture:
        # Supprimer le fichier
        request.user.profile_picture.delete()
        request.user.profile_picture = None
        request.user.save()
        messages.success(request, 'Votre photo de profil a été supprimée avec succès!')
    else:
        messages.error(request, 'Vous n\'avez pas de photo de profil à supprimer.')
    
    return redirect('profile')
