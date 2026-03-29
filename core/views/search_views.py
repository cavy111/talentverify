import os
import hmac
import hashlib
import json
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status, permissions, pagination
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from core.models import Employee, EmploymentRecord, AuditLog
from core.serializers.employee_serializers import EmployeeSerializer


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def create_audit_log(request, action, table_affected, record_id=None, 
                    old_values=None, new_values=None):
    """Create an audit log entry"""
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        table_affected=table_affected,
        record_id=record_id,
        old_values=old_values,
        new_values=new_values,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:512]
    )


def generate_name_search_hash(first_name, last_name):
    """
    Generate HMAC-SHA256 hash of lowercased full name for secure searching
    """
    search_key = os.environ.get('SEARCH_HMAC_KEY')
    if not search_key:
        raise RuntimeError("SEARCH_HMAC_KEY environment variable is not set.")
    
    full_name = f"{first_name.lower()} {last_name.lower()}"
    return hmac.new(
        search_key.encode(),
        full_name.encode(),
        hashlib.sha256
    ).hexdigest()


def check_rate_limit(ip_address, limit=30, window=60):
    """
    Check if IP has exceeded rate limit (30 requests per minute by default)
    Returns tuple (is_limited, remaining_requests)
    """
    cache_key = f"search_rate_limit:{ip_address}"
    current_time = timezone.now().timestamp()
    
    # Get current request count and timestamp from cache
    cache_data = cache.get(cache_key, {'count': 0, 'window_start': current_time})
    
    # Reset window if expired
    if current_time - cache_data['window_start'] >= window:
        cache_data = {'count': 0, 'window_start': current_time}
    
    # Check if limit exceeded
    if cache_data['count'] >= limit:
        return True, 0
    
    # Increment count and update cache
    cache_data['count'] += 1
    cache.set(cache_key, cache_data, window)
    
    remaining = limit - cache_data['count']
    return False, remaining


class SearchPagination(pagination.PageNumberPagination):
    """Custom pagination for search results"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 123
                },
                'next': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'previous': {
                    'type': 'string',
                    'nullable': True,
                    'format': 'uri'
                },
                'results': schema,
                'query_params': {
                    'type': 'object',
                    'description': 'The search parameters used'
                },
                'rate_limit': {
                    'type': 'object',
                    'properties': {
                        'remaining_requests': {'type': 'integer'},
                        'reset_in_seconds': {'type': 'integer'}
                    }
                }
            }
        }


class SearchView(APIView):
    """
    Public search endpoint with rate limiting and audit logging
    Accepts query params: name, employer, position, department, year_started, year_left
    """
    permission_classes = [permissions.AllowAny]
    pagination_class = SearchPagination
    
    def get(self, request):
        """Search employees with multiple filters"""
        ip_address = get_client_ip(request)
        
        # Check rate limiting
        is_limited, remaining = check_rate_limit(ip_address)
        if is_limited:
            return Response(
                {
                    'error': 'Rate limit exceeded',
                    'message': 'Maximum 30 requests per minute allowed',
                    'rate_limit': {
                        'remaining_requests': 0,
                        'reset_in_seconds': 60
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Extract query parameters
        query_params = {
            'name': request.query_params.get('name', '').strip(),
            'employer': request.query_params.get('employer', '').strip(),
            'position': request.query_params.get('position', '').strip(),
            'department': request.query_params.get('department', '').strip(),
            'year_started': request.query_params.get('year_started', '').strip(),
            'year_left': request.query_params.get('year_left', '').strip(),
        }
        
        # Remove empty parameters for cleaner logging
        clean_params = {k: v for k, v in query_params.items() if v}
        
        # Start with all employees
        queryset = Employee.objects.all()
        
        # Apply filters
        try:
            # Name filter using HMAC hash
            if query_params['name']:
                name_parts = query_params['name'].split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])
                else:
                    first_name = query_params['name']
                    last_name = ''
                
                name_hash = generate_name_search_hash(first_name, last_name)
                queryset = queryset.filter(name_search_hash=name_hash)
            
            # Employment record filters
            employment_filters = Q()
            
            # Employer filter
            if query_params['employer']:
                employment_filters &= Q(employment_records__company__name__icontains=query_params['employer'])
            
            # Position filter
            if query_params['position']:
                employment_filters &= Q(employment_records__role_title__icontains=query_params['position'])
            
            # Department filter
            if query_params['department']:
                employment_filters &= Q(employment_records__department__name__icontains=query_params['department'])
            
            # Year started filter
            if query_params['year_started']:
                try:
                    year = int(query_params['year_started'])
                    employment_filters &= Q(employment_records__date_started__year=year)
                except ValueError:
                    pass  # Invalid year, ignore filter
            
            # Year left filter
            if query_params['year_left']:
                try:
                    year = int(query_params['year_left'])
                    employment_filters &= Q(employment_records__date_left__year=year)
                except ValueError:
                    pass  # Invalid year, ignore filter
            
            # Apply employment filters
            if employment_filters != Q():
                queryset = queryset.filter(employment_filters).distinct()
            
        except Exception as e:
            # Log the error and return empty results
            create_audit_log(
                request=request,
                action='export',
                table_affected='search',
                new_values={'error': str(e), 'query_params': clean_params}
            )
            return Response(
                {'error': 'Search query failed', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Order results
        queryset = queryset.order_by('created_at')
        
        # Paginate results
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = EmployeeSerializer(page, many=True)
            
            # Log the search query to audit log
            create_audit_log(
                request=request,
                action='export',
                table_affected='search',
                new_values=clean_params
            )
            
            # Calculate rate limit reset time
            cache_key = f"search_rate_limit:{ip_address}"
            cache_data = cache.get(cache_key, {'window_start': timezone.now().timestamp()})
            window_start = cache_data['window_start']
            reset_in_seconds = max(0, 60 - int(timezone.now().timestamp() - window_start))
            
            return paginator.get_paginated_response({
                'results': serializer.data,
                'query_params': clean_params,
                'rate_limit': {
                    'remaining_requests': remaining,
                    'reset_in_seconds': reset_in_seconds
                }
            })
        
        # Fallback for non-paginated response
        serializer = EmployeeSerializer(queryset, many=True)
        
        # Log the search query
        create_audit_log(
            request=request,
            action='export',
            table_affected='search',
            new_values=clean_params
        )
        
        return Response({
            'results': serializer.data,
            'query_params': clean_params,
            'rate_limit': {
                'remaining_requests': remaining,
                'reset_in_seconds': 60
            }
        })
