from rest_framework import serializers
from core.models import Company, Department


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'company', 'created_at']
        read_only_fields = ['id', 'created_at']


class CompanySerializer(serializers.ModelSerializer):
    """
    Full company serializer for tv_admin users
    Includes all fields including encrypted PII data
    """
    departments = DepartmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Company
        fields = [
            'id', 
            'name', 
            'registration_date', 
            'registration_number',
            'address', 
            'contact_person', 
            'contact_phone', 
            'email',
            'employee_count', 
            'created_at', 
            'updated_at',
            'departments'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompanyPublicSerializer(serializers.ModelSerializer):
    """
    Public serializer with limited fields for public search
    Excludes PII and sensitive information
    """
    class Meta:
        model = Company
        fields = ['name', 'registration_number', 'employee_count']
