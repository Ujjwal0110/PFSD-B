from django.db import models
from django.conf import settings


class Resource(models.Model):
    """
    Core model representing an educational resource uploaded by a user.

    Lifecycle:
      1. User uploads → status = PENDING
      2. Admin reviews → status = APPROVED or REJECTED
      3. Only APPROVED resources are visible in the public browse feed.
    """

    # ── Status constants ──────────────────────────────────────────────────────
    STATUS_PENDING  = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'

    STATUS_CHOICES = (
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    )

    # ── Category constants ────────────────────────────────────────────────────
    CATEGORY_CHOICES = (
        ('mathematics',      'Mathematics'),
        ('science',          'Science'),
        ('literature',       'Literature'),
        ('history',          'History'),
        ('computer_science', 'Computer Science'),
        ('arts',             'Arts'),
        ('language',         'Language'),
        ('philosophy',       'Philosophy'),
        ('books',            'Books'),
        ('notes',            'Notes'),
        ('videos',           'Videos'),
        ('papers',           'Research Papers'),
        ('slides',           'Slides / Presentations'),
        ('other',            'Other'),
    )

    # ── Core fields ───────────────────────────────────────────────────────────
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    file        = models.FileField(upload_to='resources/%Y/%m/')
    category    = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        db_index=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploads',
    )

    # ── Status / approval ─────────────────────────────────────────────────────
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_resources',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # ── Metrics ───────────────────────────────────────────────────────────────
    download_count = models.PositiveIntegerField(default=0)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # ── Features ──────────────────────────────────────────────────────────────
    tags = models.ManyToManyField('Tag', blank=True, related_name='resources')
    
    # Optional link to a request it fulfills
    linked_request = models.ForeignKey(
        'ResourceRequest', 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='responses'
    )

    class Meta:
        db_table        = 'resources'
        ordering        = ['-created_at']
        verbose_name    = 'Resource'
        verbose_name_plural = 'Resources'
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['uploaded_by', 'status']),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"

    @property
    def file_name(self):
        """Return just the filename portion of the uploaded file path."""
        return self.file.name.split('/')[-1] if self.file else None

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return sum(r.rating for r in reviews) / len(reviews)


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)

    def __str__(self):
        return self.name


class Review(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    clarity = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], default=5)
    completeness = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], default=5)
    accuracy = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('resource', 'user')  # One review per user per resource
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.resource.title} ({self.rating}/5)"


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'resource')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} bookmarked {self.resource.title}"

class Report(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report on {self.resource.title} by {self.reported_by.username}"

class Collection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'collections'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} by {self.user.username}"

class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'collection_items'
        unique_together = ('collection', 'resource')
        ordering = ['-added_at']

class ResourceRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests')
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_fulfilled = models.BooleanField(default=False)
    fulfilled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_requests')
    fulfilled_resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_for_requests')

    class Meta:
        db_table = 'resource_requests'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class DiscussionThread(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='threads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_threads'
        ordering = ['-created_at']

    def __str__(self):
        return f"Thread on {self.resource.title} by {self.user.username}"

class DiscussionReply(models.Model):
    thread = models.ForeignKey(DiscussionThread, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussion_replies'
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.user.username} on {self.thread.id}"
