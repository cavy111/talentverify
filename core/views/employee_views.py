import os
import hmac
import hashlib
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q
from core.models import Employee, EmploymentRecord, RoleDuty, AuditLog
from core.serializers.employee_serializers import (
    EmployeeSerializer, 
    EmployeeCreateSerializer,
    EmploymentRecordSerializer, 
    EmploymentRecordCreateSerializer,
    RoleDutySerializer,
    RoleDutyCreateSerializer
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


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    EmployeeViewSet with company-scoped access and HMAC search hashing
    """
    queryset = Employee.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['employee_id_number']  # Only search non-PII fields
    ordering_fields = ['created_at', 'updated_at']
    filterset_fields = ['employee_id_number']

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        return EmployeeSerializer

    def get_queryset(self):
        """Filter employees based on user's company access"""
        user = self.request.user
        
        if user.is_authenticated and user.role == 'tv_admin':
            return Employee.objects.all()
        elif user.is_authenticated and user.company:
            # Only employees linked to this company
            return Employee.objects.filter(
                employment_records__company=user.company
            ).distinct()
        return Employee.objects.none()

    def get_permissions(self):
        """Apply permissions based on action"""
        if self.action in ['list', 'retrieve']:
            return [IsCompanyUserOrAbove | IsTalentVerifyAdmin]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsCompanyAdmin | IsTalentVerifyAdmin]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Override create to add name search hash and audit logging"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Generate name search hash
        first_name = serializer.validated_data['first_name']
        last_name = serializer.validated_data['last_name']
        name_hash = generate_name_search_hash(first_name, last_name)
        
        # Create employee with hash
        employee = Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            employee_id_number=serializer.validated_data.get('employee_id_number', ''),
            national_id=serializer.validated_data.get('national_id', ''),
            name_search_hash=name_hash
        )
        
        # Return serialized data
        response_serializer = EmployeeSerializer(employee)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='create',
            table_affected='employee',
            record_id=employee.id,
            new_values=response_serializer.data
        )
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Override update to regenerate hash if name changed and add audit logging"""
        instance = self.get_object()
        
        # Store old values for audit
        old_values = {}
        serializer = self.get_serializer(instance)
        old_values = serializer.data
        
        # Check if name is being updated
        new_first_name = request.data.get('first_name')
        new_last_name = request.data.get('last_name')
        
        if (new_first_name and new_first_name != instance.first_name) or \
           (new_last_name and new_last_name != instance.last_name):
            # Regenerate hash if name changed
            first_name = new_first_name or instance.first_name
            last_name = new_last_name or instance.last_name
            instance.name_search_hash = generate_name_search_hash(first_name, last_name)
        
        response = super().update(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='update',
            table_affected='employee',
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
            table_affected='employee',
            record_id=instance.id,
            old_values=old_values
        )
        
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def search_by_name(self, request):
        """
        Search employees by name using secure hash lookup
        Query param: name (full name to search)
        """
        name_query = request.query_params.get('name')
        if not name_query:
            return Response(
                {'error': 'name parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Generate hash for search
            name_parts = name_query.strip().split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
            else:
                first_name = name_query
                last_name = ''
            
            search_hash = generate_name_search_hash(first_name, last_name)
            
            # Search by hash
            queryset = self.get_queryset().filter(name_search_hash=search_hash)
            serializer = self.get_serializer(queryset, many=True)
            
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': 'Search failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmploymentRecordViewSet(viewsets.ModelViewSet):
    """
    EmploymentRecordViewSet scoped to user's company
    """
    queryset = EmploymentRecord.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['role_title', 'employee__employee_id_number']
    ordering_fields = ['date_started', 'date_left', 'created_at']
    filterset_fields = ['company', 'department', 'is_current', 'role_title']

    def get_serializer_class(self):
        if self.action == 'create':
            return EmploymentRecordCreateSerializer
        return EmploymentRecordSerializer

    def get_queryset(self):
        """Filter employment records based on user's company access"""
        user = self.request.user
        
        if user.is_authenticated and user.role == 'tv_admin':
            return EmploymentRecord.objects.all()
        elif user.is_authenticated and user.company:
            return EmploymentRecord.objects.filter(company=user.company)
        return EmploymentRecord.objects.none()

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
            table_affected='employment_record',
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
            table_affected='employment_record',
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
            table_affected='employment_record',
            record_id=instance.id,
            old_values=old_values
        )
        
        return super().destroy(request, *args, **kwargs)


class RoleDutyViewSet(viewsets.ModelViewSet):
    """
    RoleDutyViewSet scoped to user's company
    """
    queryset = RoleDuty.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['duty_description']
    ordering_fields = ['id']
    filterset_fields = ['employment_record']

    def get_serializer_class(self):
        if self.action == 'create':
            return RoleDutyCreateSerializer
        return RoleDutySerializer

    def get_queryset(self):
        """Filter role duties based on user's company access"""
        user = self.request.user
        
        if user.is_authenticated and user.role == 'tv_admin':
            return RoleDuty.objects.all()
        elif user.is_authenticated and user.company:
            return RoleDuty.objects.filter(
                employment_record__company=user.company
            )
        return RoleDuty.objects.none()

    def get_permissions(self):
        """Apply permissions based on action"""
        if self.action in ['list', 'retrieve']:
            return [IsCompanyUserOrAbove | IsTalentVerifyAdmin]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsCompanyAdmin | IsTalentVerifyAdmin]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Override create to add audit logging"""
        response = super().create(request, *args, **kwargs)
        
        # Create audit log
        create_audit_log(
            request=request,
            action='create',
            table_affected='role_duty',
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
            table_affected='role_duty',
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
            table_affected='role_duty',
            record_id=instance.id,
            old_values=old_values
        )
        
        return super().destroy(request, *args, **kwargs)
