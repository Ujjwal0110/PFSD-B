from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds a 'role' field to support Admin and regular User roles.
    """
    ROLE_ADMIN = 'admin'
    ROLE_USER  = 'user'
    ROLE_CHOICES = (
        (ROLE_ADMIN, 'Admin'),
        (ROLE_USER,  'User'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
        db_index=True,
    )
    
    # Gamification & Profile
    reputation_points = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True, max_length=500)
    full_name = models.CharField(max_length=255, blank=True)
    member_id = models.CharField(max_length=20, unique=True, db_index=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_shadow_banned = models.BooleanField(default=False)

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        # Auto-generate unique Member ID
        try:
            if not self.member_id:
                import random
                import string
                while True:
                    new_id = 'EDU-' + ''.join(random.choices(string.digits, k=6))
                    if not type(self).objects.filter(member_id=new_id).exists():
                        self.member_id = new_id
                        break
            
            # Auto-verify users with high reputation
            if self.reputation_points >= 500:
                self.is_verified = True
        except Exception as e:
            print(f"Error in User.save: {e}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_admin_role(self):
        """Returns True if user has the admin role."""
        return self.role == self.ROLE_ADMIN

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'follows'
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

class Notification(models.Model):
    TYPES = (
        ('approval', 'Resource Approved'),
        ('rejection', 'Resource Rejected'),
        ('fulfillment', 'Request Fulfilled'),
        ('follow', 'New Follower'),
        ('mention', 'New Mention'),
        ('system', 'System Message'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.title}"

class OTP(models.Model):
    """
    Model to store One-Time Passwords for email verification and password resets.
    """
    PURPOSE_VERIFY = 'verify'
    PURPOSE_RESET  = 'reset'
    PURPOSE_CHOICES = (
        (PURPOSE_VERIFY, 'Email Verification'),
        (PURPOSE_RESET,  'Password Reset'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'otps'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.code} ({self.purpose})"

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        # OTP expires in 10 minutes
        return timezone.now() > self.created_at + timedelta(minutes=10)
