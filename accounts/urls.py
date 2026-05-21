from django.urls import path
from . import views

urlpatterns = [
    path('delete-profile-picture/', views.delete_profile_picture, name='delete_profile_picture'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
]
