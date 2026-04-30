from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPES = (
        ('approval', 'Resource Approved'),
        ('rejection', 'Resource Rejected'),
        ('fulfillment', 'Request Fulfilled'),
        ('follow', 'New Follower'),
        ('system', 'System Message'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
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
