from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse


urlpatterns = [
    # Root URL
    path('', lambda request: HttpResponse("PFSD Backend Running Successfully")),

    # Django built-in admin panel
    path('admin/', admin.site.urls),
    path('django-admin/', admin.site.urls),

    # API routes — accounts
    path('api/', include('apps.accounts.urls')),

    # API routes — resources
    path('api/', include('apps.resources.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# ─── Customize admin site branding ───────────────────────────────────────────
admin.site.site_header = 'Edu Resource Library — Admin'
admin.site.site_title = 'DERL Admin'
admin.site.index_title = 'Welcome to the DERL Admin Panel'
