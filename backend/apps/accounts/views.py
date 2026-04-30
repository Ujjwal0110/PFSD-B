from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from django.core.mail import send_mail
from django.conf import settings
import random
import string

from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer, UserUpdateSerializer,
    PasswordUpdateSerializer, NotificationSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .models import Notification, OTP
from apps.resources.permissions import IsAdminRole

User = get_user_model()


def get_tokens_for_user(user, request=None):
    """Generate JWT access + refresh token pair for a user with custom claims."""
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['email'] = user.email
    refresh['role'] = user.role
    refresh['username'] = user.username
    refresh['reputation_points'] = user.reputation_points
    
    if user.avatar:
        avatar_url = user.avatar.url
        if request:
            avatar_url = request.build_absolute_uri(avatar_url)
        refresh['avatar'] = avatar_url
    
    return {
        'refresh': str(refresh),
        'access':  str(refresh.access_token),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/register/
# ─────────────────────────────────────────────────────────────────────────────
class RegisterView(APIView):
    """
    Register a new user account.
    Accepts: username, email, password, password2, role (optional)
    Returns: user object + JWT tokens
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                user.is_active = False # Deactivate until verified
                user.save()

                # Generate and send OTP
                code = ''.join(random.choices(string.digits, k=6))
                OTP.objects.create(user=user, code=code, purpose=OTP.PURPOSE_VERIFY)

                subject = 'Verify your email - DERL'
                display_name = user.full_name or user.username
                message = f'Hi {display_name},\n\nYour verification code is: {code}\n\nPlease enter this code to verify your account.'
                email_from = settings.DEFAULT_FROM_EMAIL
                recipient_list = [user.email]
                
                try:
                    send_mail(subject, message, email_from, recipient_list)
                except Exception as e:
                    print(f"Error sending email: {e}")
                    # In development, we might not have SMTP configured, so we just log it.
                
                return Response({
                    'message': 'Registration successful. Please check your email for the verification code.',
                    'email': user.email
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Registration failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/login/
# ─────────────────────────────────────────────────────────────────────────────
class LoginView(APIView):
    """
    Authenticate a user and return JWT tokens.
    Accepts: username, password
    Returns: user object + JWT tokens
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = LoginSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(request, username=username, password=password)

            if user is None:
                return Response(
                    {'error': 'Invalid credentials. Please check your username and password.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not user.is_active:
                return Response(
                    {'error': 'Your account is inactive. Please verify your email or contact support.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

            tokens = get_tokens_for_user(user, request)
            return Response({
                'user':    UserSerializer(user, context={'request': request}).data,
                'tokens':  tokens,
                'access':  tokens['access'],
                'refresh': tokens['refresh'],
                'message': 'Login successful.',
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f"Login failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/me/
# ─────────────────────────────────────────────────────────────────────────────
class MeView(APIView):
    """Return the currently authenticated user's profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            serializer = UserSerializer(request.user, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': f"Failed to fetch profile: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/users/<int:pk>/
# ─────────────────────────────────────────────────────────────────────────────
class PublicProfileView(APIView):
    """
    Retrieve a user's public profile and their approved resources.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            serializer = UserSerializer(user, context={'request': request})
            
            # Add resources uploaded by this user
            from apps.resources.models import Resource
            from apps.resources.serializers import ResourceSerializer
            resources = Resource.objects.filter(uploaded_by=user, status=Resource.STATUS_APPROVED)
            resource_data = ResourceSerializer(resources, many=True, context={'request': request}).data

            data = serializer.data
            data['resources'] = resource_data
            return Response(data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/logout/
# ─────────────────────────────────────────────────────────────────────────────
class LogoutView(APIView):
    """
    Blacklist the refresh token to log out the user.
    Accepts: refresh (the refresh token string)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(
                {'message': 'Logged out successfully.'},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {'error': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

class ProfileUpdateView(APIView):
    """PATCH /api/me/update/ - Update current user's profile."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        try:
            user = request.user
            serializer = UserUpdateSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                # Handle photo removal signal
                if request.data.get('remove_avatar') == 'true':
                    if user.avatar:
                        user.avatar.delete(save=False)
                        user.avatar = None
                
                serializer.save()
                return Response({
                    'message': 'Profile updated successfully.',
                    'user': UserSerializer(user, context={'request': request}).data
                })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Update failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordUpdateView(APIView):
    """PATCH /api/me/password/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        try:
            user = request.user
            serializer = PasswordUpdateSerializer(data=request.data)
            if serializer.is_valid():
                if not user.check_password(serializer.validated_data['old_password']):
                    return Response({'old_password': ['Wrong old password.']}, status=status.HTTP_400_BAD_REQUEST)
                
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                return Response({'message': 'Password updated successfully.'})
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Password update failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN USER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class AdminUserListView(APIView):
    """
    GET /api/admin/users/
    List all registered users. Admin only.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        try:
            users = User.objects.all().order_by('-date_joined')
            serializer = UserSerializer(users, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': f"Failed to list users: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminUserDeleteView(APIView):
    """
    DELETE /api/admin/users/<int:pk>/
    Delete a user account. Admin only.
    """
    permission_classes = [IsAdminRole]

    def delete(self, request, pk):
        try:
            if request.user.pk == pk:
                return Response({'error': 'You cannot delete your own admin account.'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_to_delete = User.objects.get(pk=pk)
            username = user_to_delete.username
            user_to_delete.delete()
            return Response({'message': f'User "{username}" has been deleted.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

# ─────────────────────────────────────────────────────────────────────────────
# POST /api/users/<int:pk>/follow/
# ─────────────────────────────────────────────────────────────────────────────
class FollowToggleView(APIView):
    """Toggle follow/unfollow for a user."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            target_user = User.objects.get(pk=pk)
            if target_user == request.user:
                return Response({'error': 'You cannot follow yourself.'}, status=status.HTTP_400_BAD_REQUEST)

            from .models import Follow
            follow_obj = Follow.objects.filter(follower=request.user, following=target_user).first()
            if follow_obj:
                follow_obj.delete()
                return Response({'message': f'You unfollowed {target_user.username}'}, status=status.HTTP_200_OK)
            else:
                Follow.objects.create(follower=request.user, following=target_user)
                return Response({'message': f'You are now following {target_user.username}'}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f"Follow action failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────
class NotificationListView(APIView):
    """GET /api/notifications/ - List user's notifications."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        # Limit to last 50
        notifications = notifications[:50]
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

class MarkNotificationReadView(APIView):
    """PATCH /api/notifications/mark-read/ - Mark all or specific notifications as read."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        notif_id = request.data.get('notification_id')
        if notif_id:
            Notification.objects.filter(user=request.user, pk=notif_id).update(is_read=True)
        else:
            Notification.objects.filter(user=request.user).update(is_read=True)
        return Response({'message': 'Notifications marked as read.'})

class LeaderboardView(APIView):
    """GET /api/users/leaderboard/ - Top users by reputation."""
    permission_classes = [AllowAny]

    def get(self, request):
        top_users = User.objects.order_by('-reputation_points')[:10]
        serializer = UserSerializer(top_users, many=True, context={'request': request})
        return Response(serializer.data)

class ActivityHeatmapView(APIView):
    """GET /api/users/<id>/heatmap/ - Daily activity data for heatmap."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            from django.utils import timezone
            from datetime import timedelta
            from django.db.models import Count
            from django.db.models.functions import TruncDay
            from apps.resources.models import Resource, Review
            
            user = User.objects.get(pk=pk)
            one_year_ago = timezone.now() - timedelta(days=365)
            
            # Aggregating uploads
            uploads = Resource.objects.filter(
                uploaded_by=user, 
                created_at__gte=one_year_ago
            ).annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id'))
            
            # Aggregating reviews
            reviews = Review.objects.filter(
                user=user, 
                created_at__gte=one_year_ago
            ).annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id'))
            
            # Combine
            activity_data = {}
            for item in uploads:
                day_str = item['day'].strftime('%Y-%m-%d')
                activity_data[day_str] = activity_data.get(day_str, 0) + item['count']
                
            for item in reviews:
                day_str = item['day'].strftime('%Y-%m-%d')
                activity_data[day_str] = activity_data.get(day_str, 0) + item['count']
                
            # Convert to list for frontend [{date: '...', count: ...}]
            formatted_data = [{'date': d, 'count': c} for d, c in activity_data.items()]
            
            return Response(formatted_data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Exception as e:
            return Response({'error': f"Heatmap failed: {str(e)}"}, status=500)

# ─────────────────────────────────────────────────────────────────────────────
# EMAIL VERIFICATION & PASSWORD RESET
# ─────────────────────────────────────────────────────────────────────────────

class VerifyEmailView(APIView):
    """POST /api/verify-email/"""
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({'error': 'Email and code are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email__iexact=email)
            otp = OTP.objects.filter(user=user, code=code, purpose=OTP.PURPOSE_VERIFY, is_used=False).first()

            if not otp:
                return Response({'error': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

            if otp.is_expired:
                return Response({'error': 'Verification code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

            otp.is_used = True
            otp.save()

            user.is_active = True
            user.is_verified = True
            user.save()

            tokens = get_tokens_for_user(user, request)
            return Response({
                'message': 'Email verified successfully.',
                'user': UserSerializer(user, context={'request': request}).data,
                'tokens': tokens
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ForgotPasswordView(APIView):
    """POST /api/forgot-password/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email__iexact=email)

            # Generate and send OTP
            code = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(user=user, code=code, purpose=OTP.PURPOSE_RESET)

            subject = 'Reset your password - DERL'
            display_name = user.full_name or user.username
            message = f'Hi {display_name},\n\nYour password reset code is: {code}\n\nIf you did not request this, please ignore this email.'
            email_from = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]

            try:
                send_mail(subject, message, email_from, recipient_list)
            except Exception as e:
                print(f"Error sending email: {e}")

            return Response({'message': 'Password reset code sent to your email.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    """POST /api/reset-password/"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            code = serializer.validated_data['code']
            new_password = serializer.validated_data['new_password']

            try:
                user = User.objects.get(email__iexact=email)
                otp = OTP.objects.filter(user=user, code=code, purpose=OTP.PURPOSE_RESET, is_used=False).first()

                if not otp:
                    return Response({'error': 'Invalid reset code.'}, status=status.HTTP_400_BAD_REQUEST)

                if otp.is_expired:
                    return Response({'error': 'Reset code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

                otp.is_used = True
                otp.save()

                user.set_password(new_password)
                user.save()

                return Response({'message': 'Password reset successful. You can now log in.'}, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
