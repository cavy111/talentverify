import os
import hmac
import hashlib
import json
from datetime import datetime
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.utils import timezone
from core.models import Employee, EmploymentRecord, RoleDuty, Department, AuditLog
from core.permissions import IsCompanyAdmin, IsTalentVerifyAdmin


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


def parse_date(date_str):
    """Parse date string in various formats"""
    if not date_str or str(date_str).strip() == '':
        return None
    
    date_str = str(date_str).strip()
    
    # Try common date formats
    date_formats = [
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%m-%d-%Y',
        '%Y%m%d',
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Try pandas parsing for Excel dates
    try:
        import pandas as pd
        return pd.to_datetime(date_str).date()
    except:
        pass
    
    return None


class BulkUploadView(APIView):
    """
    Bulk upload endpoint for employee data
    Supports CSV, TXT, and XLSX file formats
    """
    permission_classes = [IsCompanyAdmin | IsTalentVerifyAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Handle bulk file upload"""
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file type
        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in ['.csv', '.txt', '.xlsx']:
            return Response(
                {'error': 'Unsupported file type. Use CSV, TXT, or XLSX'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Read file based on type
            if file_extension in ['.csv', '.txt']:
                import pandas as pd
                df = pd.read_csv(file)
            elif file_extension == '.xlsx':
                import pandas as pd
                df = pd.read_excel(file, engine='openpyxl')
            
            # Process the data
            result = self.process_bulk_data(df, request.user)
            
            # Log the bulk upload
            create_audit_log(
                request=request,
                action='bulk_upload',
                table_affected='bulk_upload',
                new_values=result
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'File processing failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def process_bulk_data(self, df, user):
        """Process the bulk upload data"""
        total_rows = len(df)
        success_count = 0
        error_count = 0
        errors = []
        
        # Normalize column names (case-insensitive)
        column_mapping = {}
        expected_columns = [
            'employee_id_number', 'first_name', 'last_name', 'national_id',
            'department', 'role_title', 'date_started', 'date_left', 'duties'
        ]
        
        for col in df.columns:
            col_lower = str(col).strip().lower()
            for expected in expected_columns:
                if col_lower == expected.lower():
                    column_mapping[expected] = col
                    break
        
        # Check for required columns
        missing_columns = []
        required_columns = ['first_name', 'last_name', 'role_title', 'date_started']
        for req_col in required_columns:
            if req_col not in column_mapping:
                missing_columns.append(req_col)
        
        if missing_columns:
            return {
                'total_rows': total_rows,
                'success_count': 0,
                'error_count': total_rows,
                'errors': [{'row': 0, 'reason': f'Missing required columns: {", ".join(missing_columns)}'}]
            }
        
        # Process each row
        for index, row in df.iterrows():
            row_num = index + 2  # +2 because Excel sheets are 1-indexed and header is row 1
            
            try:
                with transaction.atomic():
                    # Extract row data
                    employee_id_number = str(row[column_mapping.get('employee_id_number', '')]).strip() if column_mapping.get('employee_id_number') else ''
                    first_name = str(row[column_mapping['first_name']]).strip()
                    last_name = str(row[column_mapping['last_name']]).strip()
                    national_id = str(row[column_mapping.get('national_id', '')]).strip() if column_mapping.get('national_id') else ''
                    department_name = str(row[column_mapping.get('department', '')]).strip() if column_mapping.get('department') else ''
                    role_title = str(row[column_mapping['role_title']]).strip()
                    date_started = parse_date(row[column_mapping['date_started']])
                    date_left = parse_date(row[column_mapping.get('date_left', '')]) if column_mapping.get('date_left') else None
                    duties_str = str(row[column_mapping.get('duties', '')]).strip() if column_mapping.get('duties') else ''
                    
                    # Validate required fields
                    if not first_name or not last_name or not role_title or not date_started:
                        errors.append({
                            'row': row_num,
                            'reason': 'Missing required fields: first_name, last_name, role_title, date_started'
                        })
                        error_count += 1
                        continue
                    
                    # Get or create employee
                    if employee_id_number:
                        employee, created = Employee.objects.get_or_create(
                            employee_id_number=employee_id_number,
                            defaults={
                                'first_name': first_name,
                                'last_name': last_name,
                                'national_id': national_id,
                                'name_search_hash': generate_name_search_hash(first_name, last_name)
                            }
                        )
                    else:
                        # Use name search hash if no employee ID
                        name_hash = generate_name_search_hash(first_name, last_name)
                        employee, created = Employee.objects.get_or_create(
                            name_search_hash=name_hash,
                            defaults={
                                'first_name': first_name,
                                'last_name': last_name,
                                'national_id': national_id,
                                'employee_id_number': ''
                            }
                        )
                    
                    # Update employee data if it existed but had different info
                    if not created:
                        update_fields = {}
                        if employee.first_name != first_name:
                            update_fields['first_name'] = first_name
                        if employee.last_name != last_name:
                            update_fields['last_name'] = last_name
                        if national_id and employee.national_id != national_id:
                            update_fields['national_id'] = national_id
                        
                        if update_fields:
                            update_fields['name_search_hash'] = generate_name_search_hash(first_name, last_name)
                            Employee.objects.filter(id=employee.id).update(**update_fields)
                    
                    # Get user's company
                    company = user.company if user.role != 'tv_admin' else None
                    if not company:
                        errors.append({
                            'row': row_num,
                            'reason': 'User must be associated with a company for bulk upload'
                        })
                        error_count += 1
                        continue
                    
                    # Get or create department
                    department = None
                    if department_name:
                        department, _ = Department.objects.get_or_create(
                            company=company,
                            name=department_name
                        )
                    
                    # Check for duplicate employment record
                    existing_record = EmploymentRecord.objects.filter(
                        employee=employee,
                        company=company,
                        role_title=role_title,
                        date_started=date_started
                    ).first()
                    
                    if existing_record:
                        # Update existing record if needed
                        update_fields = {}
                        if department and existing_record.department != department:
                            update_fields['department'] = department
                        if date_left != existing_record.date_left:
                            update_fields['date_left'] = date_left
                            update_fields['is_current'] = date_left is None
                        
                        if update_fields:
                            EmploymentRecord.objects.filter(id=existing_record.id).update(**update_fields)
                    else:
                        # Create new employment record
                        employment_record = EmploymentRecord.objects.create(
                            employee=employee,
                            company=company,
                            department=department,
                            role_title=role_title,
                            date_started=date_started,
                            date_left=date_left,
                            is_current=date_left is None
                        )
                    
                    # Process duties
                    if duties_str:
                        # Split duties by semicolon
                        duties = [duty.strip() for duty in duties_str.split(';') if duty.strip()]
                        
                        # Create role duties
                        for duty_description in duties:
                            RoleDuty.objects.get_or_create(
                                employment_record=employment_record,
                                duty_description=duty_description
                            )
                    
                    success_count += 1
                    
            except Exception as e:
                errors.append({
                    'row': row_num,
                    'reason': f'Processing error: {str(e)}'
                })
                error_count += 1
                continue
        
        return {
            'total_rows': total_rows,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors
        }
