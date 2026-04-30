from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timezone as dt_timezone, timedelta
from django.utils import timezone
from django.db.models import Q

from .permissions import IsAdminRole, IsOwnerOrAdmin
from .models import Resource, Tag, Review, Bookmark, Report
from .serializers import (
    ResourceSerializer,
    ResourceUploadSerializer,
    ResourceAdminSerializer,
    ReviewSerializer,
    BookmarkSerializer,
    ReportSerializer,
    DiscussionThreadSerializer,
    DiscussionReplySerializer,
    CollectionSerializer,
    CollectionItemSerializer,
    ResourceRequestSerializer,
)
from apps.accounts.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()


class StandardPagination(PageNumberPagination):
    """Standard 10-item pagination used across all list endpoints."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


# ─────────────────────────────────────────────────────────────────────────────
# USER ENDPOINTS (IsAuthenticated)
# ─────────────────────────────────────────────────────────────────────────────

class ResourceListView(APIView):
    """
    GET /api/resources/
    List all APPROVED resources. Supports 'q' (search) and 'category' filtering.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            queryset = Resource.objects.filter(status=Resource.STATUS_APPROVED).select_related('uploaded_by', 'approved_by').prefetch_related('tags')

            # Filter out shadow-banned users' content
            queryset = queryset.exclude(uploaded_by__is_shadow_banned=True)

            # 1. Text search
            q = request.query_params.get('q', '').strip()
            if q:
                queryset = queryset.filter(
                    Q(title__icontains=q) |
                    Q(description__icontains=q) |
                    Q(category__icontains=q)
                )

            # 2. Category filter
            category = request.query_params.get('category', '').strip()
            if category:
                queryset = queryset.filter(category=category)

            # 3. Pagination
            paginator = StandardPagination()
            page = paginator.paginate_queryset(queryset, request)
            serializer = ResourceSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            return Response({'error': f"Failed to list resources: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResourceUploadView(APIView):
    """
    POST /api/resources/upload/
    Upload a new resource. Automatically set to PENDING status.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = ResourceUploadSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                resource = serializer.save()
                # Return full resource representation upon success
                return Response(
                    ResourceSerializer(resource, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Upload failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResourceDownloadView(APIView):
    """
    POST /api/resources/download/{id}/
    Increments download count and returns the absolute file URL.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            # Can only download APPROVED resources
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            
            # Increment safely
            resource.download_count += 1
            resource.save(update_fields=['download_count'])
            
            # Award 1 point to the uploader for getting a download (if not own download)
            if resource.uploaded_by and resource.uploaded_by != request.user:
                resource.uploaded_by.reputation_points += 1
                resource.uploaded_by.save(update_fields=['reputation_points'])
            
            return Response({
                'message': 'Download count updated.',
                'download_count': resource.download_count,
                'file_url': request.build_absolute_uri(resource.file.url)
            }, status=status.HTTP_200_OK)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found or not approved.'}, status=status.HTTP_404_NOT_FOUND)


class ResourcePreviewView(APIView):
    """
    GET /api/resources/{id}/preview/
    Serves the file content directly with inline disposition.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            if not resource.file:
                return Response({'error': 'No file attached.'}, status=400)
            
            import mimetypes
            content_type, _ = mimetypes.guess_type(resource.file.path)
            
            from django.http import FileResponse
            response = FileResponse(resource.file.open(), content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{resource.file.name}"'
            return response
            
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found or not approved.'}, status=404)


class MyUploadsView(APIView):
    """
    GET /api/resources/my-uploads/
    Returns all resources uploaded by the requesting user (any status).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Resource.objects.filter(uploaded_by=request.user).select_related('approved_by').prefetch_related('tags').order_by('-created_at')
        
        # Support pagination for My Uploads as well
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ResourceSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class TopDownloadsView(APIView):
    """
    GET /api/resources/top-downloads/
    Returns top 10 most downloaded approved resources.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Resource.objects.filter(
            status=Resource.STATUS_APPROVED
        ).order_by('-download_count')[:10]
        
        serializer = ResourceSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS (IsAdminRole)
# ─────────────────────────────────────────────────────────────────────────────

class AdminAllResourcesView(APIView):
    """
    GET /api/admin/resources/
    Admin view of ALL resources across the platform, with optional status/search filters.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        queryset = Resource.objects.select_related('uploaded_by', 'approved_by').all()

        # Filter by exact status if provided
        status_filter = request.query_params.get('status', '').upper()
        if status_filter in dict(Resource.STATUS_CHOICES):
            queryset = queryset.filter(status=status_filter)

        # Search across title/desc
        q = request.query_params.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(uploaded_by__username__icontains=q)
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ResourceAdminSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminPendingResourcesView(APIView):
    """
    GET /api/admin/resources/pending/
    Admin view to easily fetch only PENDING resources.
    """
    permission_classes = [IsAdminRole]

    def get(self, request):
        queryset = Resource.objects.filter(status=Resource.STATUS_PENDING).select_related('uploaded_by').prefetch_related('tags')
        
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = ResourceAdminSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminApproveResourceView(APIView):
    """
    POST /api/admin/resources/{id}/approve/
    Approve a pending resource.
    """
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk)
            if resource.status == Resource.STATUS_APPROVED:
                return Response({'message': 'Resource already approved.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Update status
            resource.status = Resource.STATUS_APPROVED
            resource.approved_by = request.user
            resource.approved_at = timezone.now()
            resource.save(update_fields=['status', 'approved_by', 'approved_at'])
            
            # Award 10 points to uploader for getting approved
            if resource.uploaded_by:
                resource.uploaded_by.reputation_points += 10
                resource.uploaded_by.save(update_fields=['reputation_points'])

                # If resource was a response to a request, fulfill the request
                if resource.linked_request and not resource.linked_request.is_fulfilled:
                    req = resource.linked_request
                    req.is_fulfilled = True
                    req.fulfilled_by = resource.uploaded_by
                    req.fulfilled_resource = resource
                    req.save()
                    
                    # Extra bonus for fulfilling a request
                    resource.uploaded_by.reputation_points += 10
                    resource.uploaded_by.save(update_fields=['reputation_points'])
                # Create in-app notification
                try:
                    from apps.accounts.models import Notification
                    Notification.objects.create(
                        user=resource.uploaded_by,
                        type='approval',
                        title='Resource Approved! 🎉',
                        message=f'Your resource "{resource.title}" has been approved and is now live. +10 Reputation!',
                        link=f'/resources/{resource.id}'
                    )
                    
                    if resource.linked_request:
                        Notification.objects.create(
                            user=resource.uploaded_by,
                            type='fulfillment',
                            title='Request Fulfilled! 🏆',
                            message=f'You fulfilled a community request with your resource "{resource.title}". Extra +10 Reputation!',
                            link=f'/resources/{resource.id}'
                        )
                except Exception as ne:
                    print(f"Failed to create notification: {ne}")
            
            return Response({
                'message': f'Resource "{resource.title}" approved successfully.',
                'resource': ResourceAdminSerializer(resource, context={'request': request}).data
            }, status=status.HTTP_200_OK)
            
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f"Approval process failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminRejectResourceView(APIView):
    """
    POST /api/admin/resources/{id}/reject/
    Reject a pending resource.
    """
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk)
            if resource.status == Resource.STATUS_REJECTED:
                return Response({'message': 'Resource already rejected.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Update status
            resource.status = Resource.STATUS_REJECTED
            resource.approved_by = request.user
            resource.approved_at = timezone.now()
            resource.save(update_fields=['status', 'approved_by', 'approved_at'])
            
            # Create in-app notification
            try:
                from apps.accounts.models import Notification
                Notification.objects.create(
                    user=resource.uploaded_by,
                    type='rejection',
                    title='Resource Rejected ❌',
                    message=f'Your resource "{resource.title}" was not approved. Please review our guidelines.',
                    link='/my-uploads'
                )
            except Exception as e:
                print(f"Failed to create notification: {e}")
            
            # Send email notification
            if resource.uploaded_by:
                try:
                    from django.core.mail import send_mail
                    send_mail(
                        'Your Resource was Rejected',
                        f'We are sorry to inform you that your resource "{resource.title}" was rejected as it did not meet our quality guidelines.',
                        settings.DEFAULT_FROM_EMAIL,
                        [resource.uploaded_by.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Failed to send email: {e}")
            
            return Response({
                'message': f'Resource "{resource.title}" rejected.',
                'resource': ResourceAdminSerializer(resource, context={'request': request}).data
            }, status=status.HTTP_200_OK)
            
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)


class AdminResourceManageView(APIView):
    """
    DELETE /api/resources/{id}/ (Delete)
    PATCH  /api/resources/{id}/ (Partial Update)
    Permanently manage a resource. Admin only.
    """
    permission_classes = [IsAdminRole]

    def patch(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk)
            serializer = ResourceUploadSerializer(resource, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                resource = serializer.save()
                return Response(
                    ResourceSerializer(resource, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk)
            title = resource.title
            
            # Clean up the physical file to save space
            if resource.file:
                resource.file.delete(save=False)
                
            resource.delete()
            return Response(
                {'message': f'Resource "{title}" permanently deleted.'}, 
                status=status.HTTP_200_OK
            )
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

# ─────────────────────────────────────────────────────────────────────────────
# NEW FEATURE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class ResourceReviewsView(APIView):
    """
    GET /api/resources/{id}/reviews/ (List reviews)
    POST /api/resources/{id}/reviews/ (Create review)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            reviews = resource.reviews.select_related('user').all()
            serializer = ReviewSerializer(reviews, many=True)
            return Response(serializer.data)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=404)

    def post(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            if Review.objects.filter(resource=resource, user=request.user).exists():
                return Response({'error': 'You already reviewed this resource.'}, status=400)
                
            serializer = ReviewSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user, resource=resource)
                return Response(serializer.data, status=201)
            return Response(serializer.errors, status=400)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=404)


class ToggleBookmarkView(APIView):
    """POST /api/resources/{id}/bookmark/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            bookmark, created = Bookmark.objects.get_or_create(user=request.user, resource=resource)
            if not created:
                bookmark.delete()
                return Response({'message': 'Bookmark removed.', 'bookmarked': False})
            return Response({'message': 'Resource bookmarked.', 'bookmarked': True})
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=404)


class MyBookmarksView(APIView):
    """GET /api/resources/bookmarks/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookmarks = Bookmark.objects.filter(user=request.user).select_related('resource', 'resource__uploaded_by')
        resources = [b.resource for b in bookmarks]
        
        paginator = StandardPagination()
        page = paginator.paginate_queryset(resources, request)
        serializer = ResourceSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class AdminAnalyticsView(APIView):
    """GET /api/admin/analytics/"""
    permission_classes = [IsAdminRole]

    def get(self, request):
        from django.db.models import Count, Sum
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        total_users = User.objects.count()
        total_resources = Resource.objects.count()
        total_downloads = Resource.objects.aggregate(t=Sum('download_count'))['t'] or 0
        pending_approvals = Resource.objects.filter(status=Resource.STATUS_PENDING).count()
        
        # Growth data (last 7 days)
        last_7_days = timezone.now() - timedelta(days=7)
        
        user_growth = (
            User.objects.filter(date_joined__gte=last_7_days)
            .extra(select={'day': "date(date_joined)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        
        resource_growth = (
            Resource.objects.filter(created_at__gte=last_7_days)
            .extra(select={'day': "date(created_at)"})
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        category_stats = list(Resource.objects.values('category').annotate(count=Count('id')))
        reports_count = Report.objects.filter(is_resolved=False).count()

        return Response({
            'total_users': total_users,
            'total_resources': total_resources,
            'total_downloads': total_downloads,
            'pending_approvals': pending_approvals,
            'active_reports': reports_count,
            'category_stats': category_stats,
            'user_growth': list(user_growth),
            'resource_growth': list(resource_growth),
        })

class PublicStatsView(APIView):
    """GET /api/resources/public-stats/"""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.accounts.models import User
        from django.db.models import Sum
        
        # Include all resources in the total count to show platform growth
        total_users = User.objects.count()
        total_resources = Resource.objects.count()
        
        # Aggregate all downloads
        downloads_agg = Resource.objects.aggregate(total=Sum('download_count'))
        total_downloads = downloads_agg['total'] or 0
        
        # Optionally add bookmarks to 'Total Activity' or keep it separate
        # For now, let's just ensure these two are accurate based on ALL records
        
        return Response({
            'total_users': total_users,
            'total_resources': total_resources,
            'total_downloads': total_downloads,
        })

class ReportResourceView(APIView):
    """POST /api/resources/{id}/report/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            serializer = ReportSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(reported_by=request.user, resource=resource)
                return Response({'message': 'Resource reported successfully. Admins will review it soon.'}, status=201)
            return Response(serializer.errors, status=400)
        except Resource.DoesNotExist:
            return Response({'error': 'Resource not found.'}, status=404)

class CollectionsListView(APIView):
    """GET /api/resources/collections/, POST /api/resources/collections/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .serializers import CollectionSerializer
        collections = request.user.collections.all()
        serializer = CollectionSerializer(collections, many=True)
        return Response(serializer.data)

    def post(self, request):
        from .serializers import CollectionSerializer
        serializer = CollectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class CollectionDetailView(APIView):
    """GET /api/resources/collections/<id>/, POST (add item)"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from .models import Collection
        from .serializers import CollectionSerializer, CollectionItemSerializer
        try:
            collection = Collection.objects.get(pk=pk)
            if not collection.is_public and collection.user != request.user:
                return Response({'error': 'Private collection'}, status=403)
            data = CollectionSerializer(collection).data
            data['items'] = CollectionItemSerializer(collection.items.all(), many=True, context={'request': request}).data
            return Response(data)
        except Collection.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

    def post(self, request, pk):
        from .models import Collection, Resource, CollectionItem
        from .serializers import CollectionItemSerializer
        try:
            collection = Collection.objects.get(pk=pk, user=request.user)
            resource = Resource.objects.get(pk=request.data.get('resource_id'), status=Resource.STATUS_APPROVED)
            item, created = CollectionItem.objects.get_or_create(collection=collection, resource=resource)
            if created:
                return Response(CollectionItemSerializer(item, context={'request': request}).data, status=201)
            return Response({'message': 'Already in collection'}, status=200)
        except (Collection.DoesNotExist, Resource.DoesNotExist):
            return Response({'error': 'Not found'}, status=404)

    def delete(self, request, pk):
        from .models import Collection
        try:
            collection = Collection.objects.get(pk=pk, user=request.user)
            collection.delete()
            return Response(status=204)
        except Collection.DoesNotExist:
            return Response({'error': 'Collection not found'}, status=404)

class ResourceRequestListCreateView(APIView):
    """GET /api/resources/requests/, POST /api/resources/requests/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import ResourceRequest
        from .serializers import ResourceRequestSerializer
        requests = ResourceRequest.objects.all()
        paginator = StandardPagination()
        page = paginator.paginate_queryset(requests, request)
        serializer = ResourceRequestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        from .serializers import ResourceRequestSerializer
        serializer = ResourceRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class ResourceRequestFulfillView(APIView):
    """POST /api/resources/requests/<id>/fulfill/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .models import ResourceRequest, Resource
        try:
            req = ResourceRequest.objects.get(pk=pk, is_fulfilled=False)
            resource = Resource.objects.get(pk=request.data.get('resource_id'), status=Resource.STATUS_APPROVED)
            req.is_fulfilled = True
            req.fulfilled_by = request.user
            req.fulfilled_resource = resource
            req.save()
            
            # Bonus points for fulfilling
            request.user.reputation_points += 20
            request.user.save(update_fields=['reputation_points'])
            
            return Response({'message': 'Request fulfilled! You earned 20 reputation points.'}, status=200)
        except (ResourceRequest.DoesNotExist, Resource.DoesNotExist):
            return Response({'error': 'Not found or already fulfilled'}, status=404)

class DiscussionThreadListCreateView(APIView):
    """GET /api/resources/<id>/threads/, POST /api/resources/<id>/threads/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from .models import Resource, DiscussionThread
        from .serializers import DiscussionThreadSerializer
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            threads = resource.threads.all()
            serializer = DiscussionThreadSerializer(threads, many=True)
            return Response(serializer.data)
        except Resource.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

    def post(self, request, pk):
        from .models import Resource
        from .serializers import DiscussionThreadSerializer
        try:
            resource = Resource.objects.get(pk=pk, status=Resource.STATUS_APPROVED)
            serializer = DiscussionThreadSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user, resource=resource)
                return Response(serializer.data, status=201)
            return Response(serializer.errors, status=400)
        except Resource.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

class DiscussionReplyCreateView(APIView):
    """POST /api/resources/threads/<id>/reply/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .models import DiscussionThread
        from .serializers import DiscussionReplySerializer
        try:
            thread = DiscussionThread.objects.get(pk=pk)
            serializer = DiscussionReplySerializer(data=request.data)
            if serializer.is_valid():
                reply = serializer.save(user=request.user, thread=thread)
                
                # Mention Support Logic
                try:
                    import re
                    mentions = re.findall(r'@(\w+)', reply.reply)
                    for username in set(mentions):
                        try:
                            mentioned_user = User.objects.get(username=username)
                            if mentioned_user != request.user:
                                Notification.objects.create(
                                    user=mentioned_user,
                                    type='mention',
                                    title='You were mentioned! 💬',
                                    message=f'{request.user.full_name or request.user.username} mentioned you in a discussion.',
                                    link=f'/resources/{thread.resource.id}'
                                )
                        except User.DoesNotExist:
                            pass
                except Exception as me:
                    print(f"Mention parsing failed: {me}")

                return Response(serializer.data, status=201)
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response({'error': f"Reply failed: {str(e)}"}, status=500)
        except DiscussionThread.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

class DiscussionThreadManageView(APIView):
    """DELETE /api/resources/threads/<id>/ (Admin only)"""
    permission_classes = [IsAdminRole]

    def delete(self, request, pk):
        from .models import DiscussionThread
        try:
            thread = DiscussionThread.objects.get(pk=pk)
            thread.delete()
            return Response(status=204)
        except DiscussionThread.DoesNotExist:
            return Response({'error': 'Thread not found'}, status=404)

class DiscussionReplyManageView(APIView):
    """DELETE /api/resources/replies/<id>/ (Admin only)"""
    permission_classes = [IsAdminRole]

    def delete(self, request, pk):
        from .models import DiscussionReply
        try:
            reply = DiscussionReply.objects.get(pk=pk)
            reply.delete()
            return Response(status=204)
        except DiscussionReply.DoesNotExist:
            return Response({'error': 'Reply not found'}, status=404)

class ContributorAnalyticsView(APIView):
    """GET /api/resources/my-stats/ - Stats for the logged-in contributor."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            my_resources = Resource.objects.filter(uploaded_by=user)
            
            total_uploads = my_resources.count()
            approved_uploads = my_resources.filter(status=Resource.STATUS_APPROVED).count()
            total_downloads = sum(r.download_count for r in my_resources)
            
            # Category distribution
            from django.db.models import Count
            category_stats = my_resources.values('category').annotate(count=Count('id'))
            
            # Simple daily growth (last 7 days)
            from django.utils import timezone
            from datetime import timedelta
            growth = []
            for i in range(6, -1, -1):
                day = timezone.now().date() - timedelta(days=i)
                count = my_resources.filter(created_at__date=day).count()
                growth.append({'day': day.strftime('%a'), 'count': count})

            return Response({
                'total_uploads': total_uploads,
                'approved_uploads': approved_uploads,
                'total_downloads': total_downloads,
                'category_stats': category_stats,
                'upload_growth': growth
            })
        except Exception as e:
            return Response({'error': f"Analytics failed: {str(e)}"}, status=500)

class SuggestTagsView(APIView):
    """POST /api/resources/suggest-tags/ - Get AI-suggested tags based on text."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            print(f"DEBUG: SuggestTagsView request data: {request.data}")
            title = request.data.get('title', '')
            description = request.data.get('description', '')
            text = (title + ' ' + description).lower()
            
            # Simple keyword-based "AI" mock
            keywords = {
                'math': ['calculus', 'algebra', 'geometry', 'equation'],
                'science': ['biology', 'physics', 'chemistry', 'experiment'],
                'coding': ['python', 'javascript', 'react', 'programming', 'software'],
                'exam': ['midterm', 'final', 'test', 'quiz', 'solution'],
                'notes': ['summary', 'lecture', 'handwritten', 'guide']
            }
            
            suggested = []
            for tag, keys in keywords.items():
                if any(k in text for k in keys):
                    suggested.append(tag)
            
            # Add some dynamic tags if words are long enough
            words = [w for w in text.split() if len(w) > 4]
            if words:
                import random
                suggested.extend(random.sample(words, min(len(words), 1)))
            
            result = list(set(suggested))
            print(f"DEBUG: Suggested tags: {result}")
            return Response({'tags': result})
        except Exception as e:
            print(f"DEBUG: SuggestTagsView error: {str(e)}")
            return Response({'error': str(e)}, status=500)
