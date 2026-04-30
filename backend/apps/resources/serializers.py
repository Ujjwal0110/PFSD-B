from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Resource, Tag, Review, Bookmark, Report, Collection, CollectionItem, ResourceRequest, DiscussionThread, DiscussionReply

User = get_user_model()


class UploaderSerializer(serializers.ModelSerializer):
    """Minimal user data exposed for uploaded_by/approved_by fields."""
    class Meta:
        model = User
        fields = ('id', 'username', 'full_name', 'member_id', 'email', 'role', 'reputation_points', 'bio', 'avatar')

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ('id', 'resource', 'reported_by', 'reason', 'created_at', 'is_resolved')
        read_only_fields = ('reported_by', 'created_at', 'is_resolved')

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name')

class ReviewSerializer(serializers.ModelSerializer):
    user = UploaderSerializer(read_only=True)
    
    class Meta:
        model = Review
        fields = ('id', 'resource', 'user', 'rating', 'comment', 'created_at')
        read_only_fields = ('user', 'resource', 'created_at')

class BookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bookmark
        fields = ('id', 'user', 'resource', 'created_at')
        read_only_fields = ('user', 'created_at')


class ResourceSerializer(serializers.ModelSerializer):
    """
    Standard serializer for resources.
    Used for listing and downloading resources.
    """
    uploaded_by = UploaderSerializer(read_only=True)
    approved_by = UploaderSerializer(read_only=True)
    file_url    = serializers.SerializerMethodField()
    file_name   = serializers.SerializerMethodField()
    tags        = TagSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.SerializerMethodField()

    category    = serializers.CharField(source='get_category_display', read_only=True)
    category_slug = serializers.CharField(source='category', read_only=True)
    file_extension = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = (
            'id', 'title', 'description', 'file', 'file_url', 'file_name',
            'category', 'category_slug', 'tags', 'uploaded_by', 'created_at',
            'download_count', 'average_rating', 'reviews_count',
            'status', 'approved_by', 'approved_at', 'file_extension', 'is_bookmarked'
        )
        read_only_fields = (
            'id', 'uploaded_by', 'created_at', 'download_count',
            'status', 'approved_by', 'approved_at', 'average_rating', 'reviews_count'
        )

    def get_reviews_count(self, obj):
        return obj.reviews.count()

    def get_file_extension(self, obj):
        if not obj.file:
            return ""
        import os
        return os.path.splitext(obj.file.name)[1].lower()

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_name(self, obj):
        return obj.file_name

    def get_is_bookmarked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.bookmark_set.filter(user=request.user).exists()
        return False


class ResourceUploadSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for file uploads.
    Only allows title, description, file, and category.
    """
    tags_str = serializers.CharField(write_only=True, required=False, help_text="Comma separated tags")

    class Meta:
        model = Resource
        fields = ('id', 'title', 'description', 'file', 'category', 'tags_str', 'linked_request')

    def validate(self, attrs):
        linked_request = attrs.get('linked_request')
        if linked_request and linked_request.is_fulfilled:
            raise serializers.ValidationError({
                "linked_request": "This request has already been fulfilled and is now closed."
            })
        return attrs

    def create(self, validated_data):
        tags_str = validated_data.pop('tags_str', '')
        user = self.context['request'].user
        
        # Admins are auto-approved, others are PENDING
        status = Resource.STATUS_PENDING
        approved_by = None
        approved_at = None
        
        if user.role == 'admin':
            status = Resource.STATUS_APPROVED
            approved_by = user
            from django.utils import timezone
            approved_at = timezone.now()

        resource = Resource.objects.create(
            uploaded_by=user,
            status=status,
            approved_by=approved_by,
            approved_at=approved_at,
            **validated_data
        )

        # If admin uploaded this to fulfill a request, fulfill it immediately
        if status == Resource.STATUS_APPROVED and resource.linked_request:
            req = resource.linked_request
            if not req.is_fulfilled:
                req.is_fulfilled = True
                req.fulfilled_by = user
                req.fulfilled_resource = resource
                req.save()
        
        # Process tags
        if tags_str:
            tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(name=name.lower())
                resource.tags.add(tag)
                
        return resource


class ResourceAdminSerializer(serializers.ModelSerializer):
    """
    Full serializer for Admin views, containing all possible fields.
    """
    uploaded_by = UploaderSerializer(read_only=True)
    approved_by = UploaderSerializer(read_only=True)
    file_url    = serializers.SerializerMethodField()
    file_name   = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = '__all__'

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_file_name(self, obj):
        return obj.file_name

class CollectionSerializer(serializers.ModelSerializer):
    user = UploaderSerializer(read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = ('id', 'user', 'name', 'description', 'is_public', 'created_at', 'updated_at', 'item_count')
        read_only_fields = ('user', 'created_at', 'updated_at', 'item_count')

    def get_item_count(self, obj):
        return obj.items.count()

class CollectionItemSerializer(serializers.ModelSerializer):
    resource = ResourceSerializer(read_only=True)

    class Meta:
        model = CollectionItem
        fields = ('id', 'collection', 'resource', 'added_at')
        read_only_fields = ('collection', 'resource', 'added_at')

class ResourceRequestSerializer(serializers.ModelSerializer):
    user = UploaderSerializer(read_only=True)
    fulfilled_by = UploaderSerializer(read_only=True)
    fulfilled_resource = ResourceSerializer(read_only=True)

    class Meta:
        model = ResourceRequest
        fields = ('id', 'user', 'title', 'description', 'created_at', 'is_fulfilled', 'fulfilled_by', 'fulfilled_resource')
        read_only_fields = ('user', 'created_at', 'is_fulfilled', 'fulfilled_by', 'fulfilled_resource')

class DiscussionReplySerializer(serializers.ModelSerializer):
    user = UploaderSerializer(read_only=True)

    class Meta:
        model = DiscussionReply
        fields = ('id', 'thread', 'user', 'reply', 'created_at')
        read_only_fields = ('thread', 'user', 'created_at')

class DiscussionThreadSerializer(serializers.ModelSerializer):
    user = UploaderSerializer(read_only=True)
    replies = DiscussionReplySerializer(many=True, read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = ('id', 'resource', 'user', 'question', 'created_at', 'replies', 'replies_count')
        read_only_fields = ('resource', 'user', 'created_at', 'replies', 'replies_count')

    def get_replies_count(self, obj):
        return obj.replies.count()
