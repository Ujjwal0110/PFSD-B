from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Customized admin panel for User management.
    Shows role, email, and account status at a glance.
    """
    list_display  = ('username', 'email', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter   = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering      = ('-date_joined',)

    # Add 'role' field to the edit form
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Permissions', {'fields': ('role',)}),
    )

    # Add 'role' field to the add/create form
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

    # Allow toggling active status directly from list view
    list_editable = ('role', 'is_active')

    actions = ['make_admin', 'make_user', 'deactivate_users', 'activate_users']

    def make_admin(self, request, queryset):
        queryset.update(role='admin', is_staff=True)
    make_admin.short_description = 'Set selected users as Admin'

    def make_user(self, request, queryset):
        queryset.update(role='user')
    make_user.short_description = 'Set selected users as regular User'

    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_users.short_description = 'Deactivate selected users'

    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
    activate_users.short_description = 'Activate selected users'
