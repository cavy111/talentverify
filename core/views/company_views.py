from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from core.models import Company, Department, AuditLog
from core.serializers.company_serializers import (
    CompanySerializer, 
    CompanyPublicSerializer, 
    DepartmentSerializer
)
from core.permissions import IsTalentVerifyAdmin, IsCompanyAdmin, IsCompanyUserOrAbove


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


class CompanyViewSet(viewsets.ModelViewSet):
    """
    CompanyViewSet with role-based permissions:
    - tv_admin: full CRUD
    - company_admin: read-only + own-company update
    """
    queryset = Company.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'registration_number']
    ordering_fields = ['name', 'created_at', 'employee_count']
    filterset_fields = ['registration_number']

    def get_serializer_class(self):
        """Return appropriate serializer based on user role"""
        user = self.request.user
        if user.is_authenticated and user.role == 'tv_admin':
            return CompanySerializer
        return CompanyPublicSerializer

    def get_permissions(self):
        """Apply permissions based on action"""
        if self.action in ['list', 'retrieve']:
            # Anyone can view, but tv_admin sees full data
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            # Only company_admin can update their own company, tv_admin can update any
            return [IsTalentVerifyAdmin | IsCompanyAdmin]
        elif self.action in ['create', 'destroy']:
            # Only tv_admin can create/delete companies
            return [IsTalentVerifyAdmin]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        """Override update to add audit logging"""
        instance = self.get_object()
        
        # Check permissions for company_admin (can only update own company)
        if (request.user.role == 'company_admin' and 
            request.user.company != instance):
            return Response(
                {'error': 'You can only update your own company'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Store old values for audit
        old_values = {}
        serializer = self.get_serializer(instance)
        for field in serializer.data:
            if hasattr(instance, field):
                old_values[field] = getattr(instance, field)
        
        response = super().update(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='update',
            table_affected='company',
            record_id=instance.id,
            old_values=old_values,
            new_values=response.data
        )
        
        return response

    def create(self, request, *args, **kwargs):
        """Override create to add audit logging"""
        response = super().create(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='create',
            table_affected='company',
            record_id=response.data['id'],
            new_values=response.data
        )
        
        return response

    def destroy(self, request, *args, **kwargs):
        """Override destroy to add audit logging"""
        instance = self.get_object()
        
        # Store old values for audit
        old_values = {}
        serializer = self.get_serializer(instance)
        old_values = serializer.data
        
        # Create audit log before deletion
        create_audit_log(
            request=request,
            action='delete',
            table_affected='company',
            record_id=instance.id,
            old_values=old_values
        )
        
        return super().destroy(request, *args, **kwargs)


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    DepartmentViewSet scoped to user's company
    """
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    filterset_fields = ['company']

    def get_queryset(self):
        """Filter departments by user's company"""
        user = self.request.user
        if user.is_authenticated and user.role == 'tv_admin':
            return Department.objects.all()
        elif user.is_authenticated and user.company:
            return Department.objects.filter(company=user.company)
        return Department.objects.none()

    def get_permissions(self):
        """Apply permissions based on action"""
        if self.action in ['list', 'retrieve']:
            return [IsCompanyUserOrAbove | IsTalentVerifyAdmin]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsCompanyAdmin | IsTalentVerifyAdmin]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        """Set company based on user for non-tv_admin users"""
        user = self.request.user
        if user.role != 'tv_admin' and user.company:
            serializer.save(company=user.company)
        else:
            serializer.save()

    def create(self, request, *args, **kwargs):
        """Override create to add audit logging"""
        response = super().create(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='create',
            table_affected='department',
            record_id=response.data['id'],
            new_values=response.data
        )
        
        return response

    def update(self, request, *args, **kwargs):
        """Override update to add audit logging"""
        instance = self.get_object()
        
        # Store old values for audit
        old_values = {}
        serializer = self.get_serializer(instance)
        old_values = serializer.data
        
        response = super().update(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='update',
            table_affected='department',
            record_id=instance.id,
            old_values=old_values,
            new_values=response.data
        )
        
        return response

    def destroy(self, request, *args, **kwargs):
        """Override destroy to add audit logging"""
        instance = self.get_object()
        
        # Store old values for audit
        old_values = {}
        serializer = self.get_serializer(instance)
        old_values = serializer.data
        
        # Create audit log before deletion
        create_audit_log(
            request=request,
            action='delete',
            table_affected='department',
            record_id=instance.id,
            old_values=old_values
        )
        
        return super().destroy(request, *args, **kwargs)
