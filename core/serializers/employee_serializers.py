from rest_framework import serializers
from core.models import Employee, EmploymentRecord, RoleDuty, Department


class RoleDutySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleDuty
        fields = ['id', 'duty_description', 'employment_record']
        read_only_fields = ['id']


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'company']
        read_only_fields = ['id']


class EmploymentRecordSerializer(serializers.ModelSerializer):
    duties = RoleDutySerializer(many=True, read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = EmploymentRecord
        fields = [
            'id',
            'employee',
            'company',
            'department',
            'department_name',
            'company_name',
            'role_title',
            'date_started',
            'date_left',
            'is_current',
            'created_at',
            'updated_at',
            'duties'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeSerializer(serializers.ModelSerializer):
    employment_records = EmploymentRecordSerializer(many=True, read_only=True)
    current_employment = EmploymentRecordSerializer(read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id',
            'first_name',
            'last_name',
            'employee_id_number',
            'national_id',
            'created_at',
            'updated_at',
            'name_search_hash',
            'employment_records',
            'current_employment'
        ]
        read_only_fields = [
            'id', 
            'created_at', 
            'updated_at', 
            'name_search_hash'
        ]


class EmployeeCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating employees - includes all fields needed for creation
    """
    class Meta:
        model = Employee
        fields = [
            'first_name',
            'last_name',
            'employee_id_number',
            'national_id',
        ]


class EmploymentRecordCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating employment records
    """
    class Meta:
        model = EmploymentRecord
        fields = [
            'employee',
            'company',
            'department',
            'role_title',
            'date_started',
            'date_left',
        ]


class RoleDutyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating role duties
    """
    class Meta:
        model = RoleDuty
        fields = [
            'employment_record',
            'duty_description',
        ]
