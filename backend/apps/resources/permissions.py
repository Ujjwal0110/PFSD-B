from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Grants access only to authenticated users with role='admin'.
    Used for all admin-only API endpoints.
    """
    message = 'Access restricted to Admin users only.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission.
    - Admin users can access any resource.
    - Regular users can only access their own resources.
    """
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        # Admin can access everything
        if request.user.role == 'admin':
            return True
        # Owner can access their own uploads
        return obj.uploaded_by == request.user
