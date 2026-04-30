from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Validates that passwords match and creates the user securely.
    """
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8, label='Confirm Password', required=False)

    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'password', 'password2', 'role', 'full_name')
        extra_kwargs = {
            'email': {'required': True},
            'role':  {'required': False},
            'username': {'required': False},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        import re
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        return value

    def validate(self, attrs):
        # Allow missing password2 for TS frontend compatibility
        password2_val = attrs.pop('password2', attrs.get('password'))
        if attrs.get('password') != password2_val:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
            
        # Automatically set username from email if not provided
        if 'username' not in attrs:
            email = attrs.get('email', '')
            attrs['username'] = email.split('@')[0] + str(User.objects.count() + 1)
            
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for validating login credentials and CAPTCHA."""
    username = serializers.CharField(required=False)
    email = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)
    captcha_id = serializers.CharField(write_only=True, required=False)
    captcha_answer = serializers.CharField(write_only=True, required=False)
    
    def validate(self, attrs):
        from django.core.cache import cache
        captcha_id = attrs.get('captcha_id')
        captcha_answer = attrs.get('captcha_answer')
        
        # Only validate captcha if it's provided (for backwards compatibility with TS frontend)
        if captcha_id and captcha_answer is not None:
            expected_answer = cache.get(f"captcha_{captcha_id}")
            if expected_answer is None:
                raise serializers.ValidationError({'captcha': 'CAPTCHA expired or invalid. Please refresh.'})
                
            if str(expected_answer).upper() != str(captcha_answer).upper():
                raise serializers.ValidationError({'captcha': 'Incorrect CAPTCHA answer.'})
                
            cache.delete(f"captcha_{captcha_id}")
            
        # Handle email login from TS frontend
        email = attrs.get('email')
        if email and not attrs.get('username'):
            user = User.objects.filter(email__iexact=email).first()
            if user:
                attrs['username'] = user.username
            else:
                attrs['username'] = email # Will fail authenticate safely
                
        return attrs

class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for returning user profile data.
    Safe to send to frontend (no passwords).
    """
    is_following = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ('id', 'username', 'full_name', 'member_id', 'email', 'role', 'date_joined', 'is_active', 'reputation_points', 'bio', 'avatar', 'is_following', 'is_verified')
        read_only_fields = fields

    def get_is_following(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        from .models import Follow
        return Follow.objects.filter(follower=request.user, following=obj).exists()

class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile (bio, avatar)."""
    class Meta:
        model = User
        fields = ('bio', 'avatar')

class PasswordUpdateSerializer(serializers.Serializer):
    """Serializer for password change."""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})
        return attrs

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ('user', 'created_at')

class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for requesting password reset OTP."""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        if not User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("No user found with this email.")
        return value.lower()

class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting password using OTP."""
    email = serializers.EmailField(required=True)
    code = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(min_length=8, required=True)
    confirm_password = serializers.CharField(min_length=8, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs
