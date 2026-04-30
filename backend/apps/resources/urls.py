from django.urls import path
from .views import (
    # User endpoints
    ResourceListView,
    ResourceUploadView,
    ResourceDownloadView,
    ResourcePreviewView,
    MyUploadsView,
    TopDownloadsView,
    
    # Admin endpoints
    AdminAllResourcesView,
    AdminPendingResourcesView,
    AdminApproveResourceView,
    AdminRejectResourceView,
    AdminResourceManageView,
    
    # New feature endpoints
    ResourceReviewsView,
    ToggleBookmarkView,
    MyBookmarksView,
    AdminAnalyticsView,
    ReportResourceView,
    PublicStatsView,
    ContributorAnalyticsView,
    SuggestTagsView,

    CollectionsListView,
    CollectionDetailView,
    ResourceRequestListCreateView,
    ResourceRequestFulfillView,
    DiscussionThreadListCreateView,
    DiscussionThreadManageView,
    DiscussionReplyCreateView,
    DiscussionReplyManageView,
)

urlpatterns = [
    # ── User / General endpoints ──
    path('resources/',                 ResourceListView.as_view(),     name='resource-list'),
    path('resources/upload/',          ResourceUploadView.as_view(),   name='resource-upload'),
    path('resources/my-uploads/',      MyUploadsView.as_view(),        name='my-uploads'),
    path('resources/top-downloads/',   TopDownloadsView.as_view(),     name='top-downloads'),
    path('resources/download/<int:pk>/', ResourceDownloadView.as_view(), name='resource-download'),
    path('resources/<int:pk>/preview/',  ResourcePreviewView.as_view(),  name='resource-preview'),
    path('resources/bookmarks/',       MyBookmarksView.as_view(),      name='my-bookmarks'),
    path('resources/<int:pk>/reviews/', ResourceReviewsView.as_view(), name='resource-reviews'),
    path('resources/<int:pk>/bookmark/', ToggleBookmarkView.as_view(), name='toggle-bookmark'),
    path('resources/<int:pk>/report/',  ReportResourceView.as_view(),  name='resource-report'),
    path('resources/public-stats/',    PublicStatsView.as_view(),     name='public-stats'),
    path('resources/my-stats/',        ContributorAnalyticsView.as_view(), name='contributor-stats'),
    path('resources/suggest-tags/',    SuggestTagsView.as_view(),      name='suggest-tags'),
    
    # Collections
    path('resources/collections/', CollectionsListView.as_view(), name='collections-list'),
    path('resources/collections/<int:pk>/', CollectionDetailView.as_view(), name='collection-detail'),
    
    # Requests
    path('resources/requests/', ResourceRequestListCreateView.as_view(), name='requests-list'),
    path('resources/requests/<int:pk>/fulfill/', ResourceRequestFulfillView.as_view(), name='request-fulfill'),
    
    # Discussions
    path('resources/<int:pk>/threads/', DiscussionThreadListCreateView.as_view(), name='resource-threads'),
    path('resources/threads/<int:pk>/',  DiscussionThreadManageView.as_view(),     name='thread-manage'),
    path('resources/threads/<int:pk>/reply/', DiscussionReplyCreateView.as_view(), name='thread-reply'),
    path('resources/replies/<int:pk>/',  DiscussionReplyManageView.as_view(),      name='reply-manage'),

    # Manage (Delete/Update) uses the base resource URL in frontend AdminResources.jsx
    path('resources/<int:pk>/',        AdminResourceManageView.as_view(), name='resource-manage'),

    # ── Admin endpoints ──
    path('admin/resources/',                 AdminAllResourcesView.as_view(),     name='admin-all-resources'),
    path('admin/resources/pending/',         AdminPendingResourcesView.as_view(), name='admin-pending'),
    path('admin/resources/<int:pk>/approve/', AdminApproveResourceView.as_view(), name='admin-approve'),
    path('admin/resources/<int:pk>/reject/',  AdminRejectResourceView.as_view(),  name='admin-reject'),
    path('admin/analytics/',                  AdminAnalyticsView.as_view(),       name='admin-analytics'),
]
