from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, MeView, LogoutView, PublicProfileView, 
    FollowToggleView, AdminUserListView, AdminUserDeleteView, 
    ProfileUpdateView, PasswordUpdateView, NotificationListView, 
    MarkNotificationReadView, LeaderboardView, ActivityHeatmapView,
    VerifyEmailView, ForgotPasswordView, ResetPasswordView
)
from .captcha import CaptchaView

urlpatterns = [
    # Auth endpoints
    path('register/',      RegisterView.as_view(),  name='register'),
    path('login/',         LoginView.as_view(),     name='login'),
    path('logout/',        LogoutView.as_view(),    name='logout'),
    path('me/',            MeView.as_view(),        name='me'),
    path('me/update/',     ProfileUpdateView.as_view(), name='profile_update'),
    path('me/password/',   PasswordUpdateView.as_view(), name='password_update'),
    path('captcha/',       CaptchaView.as_view(),   name='captcha'),
    path('verify-email/',  VerifyEmailView.as_view(), name='verify_email'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/',  ResetPasswordView.as_view(), name='reset_password'),
    
    # User Profile & Follows
    path('users/leaderboard/',     LeaderboardView.as_view(),   name='leaderboard'),
    path('users/<int:pk>/heatmap/', ActivityHeatmapView.as_view(), name='user_heatmap'),
    path('users/<int:pk>/',        PublicProfileView.as_view(), name='public_profile'),
    path('users/<int:pk>/follow/', FollowToggleView.as_view(),  name='follow_toggle'),
    
    # Admin User Management
    path('admin/users/',           AdminUserListView.as_view(),   name='admin_user_list'),
    path('admin/users/<int:pk>/',  AdminUserDeleteView.as_view(), name='admin_user_delete'),

    # JWT token refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Notifications
    path('notifications/', NotificationListView.as_view(), name='notifications'),
    path('notifications/mark-read/', MarkNotificationReadView.as_view(), name='mark_notifications_read'),
]
