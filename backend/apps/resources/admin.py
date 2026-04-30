from django.contrib import admin
from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Resource model.
    Provides easy filtering, searching, and bulk approval actions.
    """
    list_display  = ('title', 'category', 'uploaded_by', 'status', 'download_count', 'created_at')
    list_filter   = ('status', 'category', 'created_at')
    search_fields = ('title', 'description', 'uploaded_by__username', 'uploaded_by__email')
    
    readonly_fields = ('created_at', 'updated_at', 'download_count', 'approved_at', 'approved_by')
    
    # Custom bulk actions
    actions = ['approve_resources', 'reject_resources']

    def approve_resources(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status=Resource.STATUS_APPROVED, 
            approved_by=request.user, 
            approved_at=timezone.now()
        )
        self.message_user(request, f"{updated} resources successfully approved.")
    approve_resources.short_description = 'Approve selected resources'

    def reject_resources(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status=Resource.STATUS_REJECTED, 
            approved_by=request.user, 
            approved_at=timezone.now()
        )
        self.message_user(request, f"{updated} resources successfully rejected.")
    reject_resources.short_description = 'Reject selected resources'
