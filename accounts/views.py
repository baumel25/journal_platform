from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import user_has_device, devices_for_user
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
from .forms import RegistrationForm, UserProfileForm
from .models import CustomUser

def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    from articles.models import Article
    from .models import CustomUser
    
    context = {
        'total_articles': Article.objects.count(),
        'published_articles': Article.objects.filter(status='published').count(),
        'total_authors': CustomUser.objects.filter(role='author').count(),
        'total_reviewers': CustomUser.objects.filter(role='reviewer').count(),
    }
    return render(request, 'accounts/home.html', context)

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
                # Check if user has 2FA enabled
                if user_has_device(user):
                    # Store user ID in session for 2FA verification
                    request.session['2fa_user_id'] = user.id
                    return redirect('verify_2fa_login')
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
    
    # Check 2FA status
    has_2fa = user_has_device(request.user)
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'has_2fa': has_2fa,
    })

@login_required
def delete_profile_picture(request):
    """Delete the profile picture"""
    if request.user.profile_picture:
        # Delete the file
        request.user.profile_picture.delete()
        request.user.profile_picture = None
        request.user.save()
        messages.success(request, 'Your profile picture has been deleted successfully!')
    else:
        messages.error(request, 'You do not have a profile picture to delete.')
    
    return redirect('profile')


# ─── Multi-Factor Authentication Views ───────────────────────────────────────

@login_required
def enable_2fa(request):
    """Set up TOTP two-factor authentication for the user."""
    # Check if already enabled
    if user_has_device(request.user):
        messages.info(request, 'Two-factor authentication is already enabled.')
        return redirect('profile')
    
    # Generate a new TOTP device (not confirmed yet)
    device, created = TOTPDevice.objects.get_or_create(
        user=request.user,
        name='default',
        defaults={'confirmed': False}
    )
    
    if not created and device.confirmed:
        messages.info(request, 'Two-factor authentication is already enabled.')
        return redirect('profile')
    
    # Generate QR code
    otp_url = device.config_url
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(otp_url, image_factory=factory, box_size=10)
    stream = BytesIO()
    img.save(stream)
    qr_svg = base64.b64encode(stream.getvalue()).decode()
    
    context = {
        'qr_svg': qr_svg,
        'device': device,
        'secret_key': device.key,  # Show backup key
    }
    return render(request, 'accounts/enable_2fa.html', context)


@login_required
def verify_2fa_setup(request):
    """Verify the TOTP code to confirm 2FA setup."""
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if not device:
        messages.error(request, 'No pending two-factor setup found.')
        return redirect('profile')
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if device.verify_token(token):
            device.confirmed = True
            device.save()
            messages.success(request, 'Two-factor authentication has been enabled successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Invalid code. Please try again.')
    
    return render(request, 'accounts/verify_2fa_setup.html', {'device': device})


@login_required
def disable_2fa(request):
    """Disable two-factor authentication."""
    if request.method == 'POST':
        devices = devices_for_user(request.user)
        for device in devices:
            device.delete()
        messages.success(request, 'Two-factor authentication has been disabled.')
        return redirect('profile')
    
    return render(request, 'accounts/disable_2fa.html')


def verify_2fa_login(request):
    """Verify OTP code during login."""
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please login again.')
        return redirect('login')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
        
        if device and device.verify_token(token):
            login(request, user)
            del request.session['2fa_user_id']
            messages.success(request, f'Welcome back {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    return render(request, 'accounts/verify_2fa_login.html', {'user': user})
