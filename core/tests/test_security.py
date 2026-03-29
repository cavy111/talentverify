import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch
from core.models import Company, Employee, EmploymentRecord, Department, AuditLog
from cryptography.fernet import Fernet

User = get_user_model()


class SecurityTestCase(TestCase):
    def setUp(self):
        """Set up test data for security tests"""
        # Create encryption key for testing
        self.test_encryption_key = Fernet.generate_key()
        
        # Create test companies
        self.company1 = Company.objects.create(
            name="Company One",
            registration_number="REG001",
            address="123 Test St",
            contact_phone="555-1234",
            email="test1@company.com"
        )
        
        self.company2 = Company.objects.create(
            name="Company Two", 
            registration_number="REG002",
            address="456 Test Ave",
            contact_phone="555-5678",
            email="test2@company.com"
        )
        
        # Create test users
        self.tv_admin = User.objects.create_user(
            email="admin@talentverify.com",
            password="adminpass123",
            role="tv_admin",
            is_staff=True,
            is_superuser=True
        )
        
        self.company_admin1 = User.objects.create_user(
            email="admin1@company.com",
            password="companypass123",
            role="company_admin",
            company=self.company1
        )
        
        self.company_user1 = User.objects.create_user(
            email="user1@company.com",
            password="userpass123",
            role="company_user",
            company=self.company1
        )
        
        self.company_admin2 = User.objects.create_user(
            email="admin2@company.com",
            password="companypass456",
            role="company_admin",
            company=self.company2
        )
        
        # Create test employees
        self.employee1 = Employee.objects.create(
            first_name="John",
            last_name="Doe",
            employee_id_number="EMP001",
            national_id="ID001"
        )
        
        self.employee2 = Employee.objects.create(
            first_name="Jane",
            last_name="Smith",
            employee_id_number="EMP002",
            national_id="ID002"
        )
        
        # Create employment records
        self.dept1 = Department.objects.create(
            company=self.company1,
            name="Engineering"
        )
        
        self.employment1 = EmploymentRecord.objects.create(
            employee=self.employee1,
            company=self.company1,
            department=self.dept1,
            role_title="Software Engineer",
            date_started="2020-01-15"
        )
        
        self.employment2 = EmploymentRecord.objects.create(
            employee=self.employee2,
            company=self.company2,
            role_title="Marketing Manager",
            date_started="2019-06-01"
        )
        
        self.client = Client()


class AuthenticationSecurityTests(SecurityTestCase):
    """Test authentication and authorization security"""
    
    def test_unauthenticated_employee_access_returns_401(self):
        """Test that unauthenticated users cannot access employee endpoints"""
        # Try to access employees without authentication
        response = self.client.get('/api/employees/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to access specific employee without authentication
        response = self.client.get(f'/api/employees/{self.employee1.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try to create employee without authentication
        response = self.client.post('/api/employees/', {
            'first_name': 'Test',
            'last_name': 'User',
            'employee_id_number': 'TEST001'
        }, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_company_admin_cannot_access_other_company_employees(self):
        """Test that company admin cannot access employees from other companies"""
        # Login as company admin 1
        response = self.client.post('/api/auth/login/', {
            'email': 'admin1@company.com',
            'password': 'companypass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Should be able to access own company employee
        response = self.client.get(f'/api/employees/{self.employee1.id}/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should NOT be able to access other company employee
        response = self.client.get(f'/api/employees/{self.employee2.id}/', **headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Employee list should only show own company employees
        response = self.client.get('/api/employees/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employees = response.json()['results']
        self.assertEqual(len(employees), 1)
        self.assertEqual(employees[0]['id'], str(self.employee1.id))
    
    @patch('core.views.auth_views.ratelimit')
    def test_brute_force_login_blocked_after_5_attempts(self, mock_ratelimit):
        """Test that login is blocked after 5 failed attempts"""
        # Mock rate limit to return False after 5 attempts
        call_count = 0
        def mock_rate_limit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return call_count <= 5
        
        mock_ratelimit.return_value = mock_rate_limit()
        
        # Make 5 failed login attempts
        for i in range(5):
            response = self.client.post('/api/auth/login/', {
                'email': 'admin@talentverify.com',
                'password': 'wrongpassword'
            }, content_type='application/json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 6th attempt should be rate limited
        response = self.client.post('/api/auth/login/', {
            'email': 'admin@talentverify.com',
            'password': 'wrongpassword'
        }, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTED)
    
    def test_bulk_upload_rejects_non_staff_user(self):
        """Test that non-staff users cannot access bulk upload"""
        # Login as regular company user
        response = self.client.post('/api/auth/login/', {
            'email': 'user1@company.com',
            'password': 'userpass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Try to access bulk upload endpoint
        response = self.client.post('/api/bulk-upload/', {}, **headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Login as company admin (should be allowed)
        response = self.client.post('/api/auth/login/', {
            'email': 'admin1@company.com',
            'password': 'companypass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Should be able to access the endpoint (even if file is invalid)
        response = self.client.post('/api/bulk-upload/', {}, **headers)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuditLogSecurityTests(SecurityTestCase):
    """Test audit logging functionality"""
    
    def test_audit_log_created_on_employee_update(self):
        """Test that audit log is created when employee is updated"""
        # Login as company admin
        response = self.client.post('/api/auth/login/', {
            'email': 'admin1@company.com',
            'password': 'companypass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Count audit logs before update
        initial_count = AuditLog.objects.count()
        
        # Update employee
        response = self.client.patch(f'/api/employees/{self.employee1.id}/', {
            'first_name': 'John Updated',
            'last_name': 'Doe Updated'
        }, content_type='application/json', **headers)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that audit log was created
        final_count = AuditLog.objects.count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Get the created audit log
        audit_log = AuditLog.objects.latest('timestamp')
        self.assertEqual(audit_log.action, 'update')
        self.assertEqual(audit_log.table_affected, 'employee')
        self.assertEqual(audit_log.record_id, self.employee1.id)
        self.assertEqual(audit_log.actor, self.company_admin1)
        self.assertIsNotNone(audit_log.new_values)
        self.assertIsNotNone(audit_log.ip_address)


class RateLimitSecurityTests(SecurityTestCase):
    """Test rate limiting functionality"""
    
    @patch('core.views.search_views.check_rate_limit')
    def test_search_rate_limit_enforced(self, mock_check_rate_limit):
        """Test that search rate limiting is enforced"""
        # Mock rate limit to return True (limited) after 30 requests
        call_count = 0
        def mock_limit_check(ip_address, limit=30, window=60):
            nonlocal call_count
            call_count += 1
            return call_count > 30
        
        mock_check_rate_limit.return_value = mock_limit_check()
        
        # Make 30 successful search requests
        for i in range(30):
            response = self.client.get('/api/search/?name=John')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTED)
        
        # 31st request should be rate limited
        response = self.client.get('/api/search/?name=John')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTED)
        self.assertIn('Rate limit exceeded', response.json()['error'])


class DataSecurityTests(SecurityTestCase):
    """Test data security and encryption"""
    
    def test_sensitive_data_encrypted_in_database(self):
        """Test that sensitive data is encrypted in database"""
        # Create a new employee with sensitive data
        employee = Employee.objects.create(
            first_name="Sensitive",
            last_name="Data",
            employee_id_number="SENSITIVE001",
            national_id="VERYSENSITIVE123"
        )
        
        # Check that the data in database is not plaintext
        employee.refresh_from_db()
        
        # The fields should be encrypted (not equal to plaintext)
        self.assertNotEqual(employee.first_name, "Sensitive")
        self.assertNotEqual(employee.last_name, "Data")
        self.assertNotEqual(employee.national_id, "VERYSENSITIVE123")
        
        # But the decrypted values should be correct
        self.assertEqual(str(employee.first_name), "Sensitive")
        self.assertEqual(str(employee.last_name), "Data")
        self.assertEqual(str(employee.national_id), "VERYSENSITIVE123")
    
    def test_company_data_isolation(self):
        """Test that companies cannot access each other's data"""
        # Login as company admin 1
        response = self.client.post('/api/auth/login/', {
            'email': 'admin1@company.com',
            'password': 'companypass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Try to access company 2 data
        response = self.client.get(f'/api/companies/{self.company2.id}/', **headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to access company 2 departments
        response = self.client.get('/api/departments/', **headers)
        departments = response.json()['results']
        for dept in departments:
            self.assertEqual(dept['company'], str(self.company1.id))


class PermissionSecurityTests(SecurityTestCase):
    """Test permission-based security"""
    
    def test_company_user_read_only_access(self):
        """Test that company users have read-only access"""
        # Login as company user
        response = self.client.post('/api/auth/login/', {
            'email': 'user1@company.com',
            'password': 'userpass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Should be able to read employees
        response = self.client.get('/api/employees/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should NOT be able to create employees
        response = self.client.post('/api/employees/', {
            'first_name': 'Unauthorized',
            'last_name': 'User',
            'employee_id_number': 'UNAUTH001'
        }, content_type='application/json', **headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Should NOT be able to update employees
        response = self.client.patch(f'/api/employees/{self.employee1.id}/', {
            'first_name': 'Hacked'
        }, content_type='application/json', **headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Should NOT be able to delete employees
        response = self.client.delete(f'/api/employees/{self.employee1.id}/', **headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_tv_admin_full_access(self):
        """Test that TV admin has full access to all data"""
        # Login as TV admin
        response = self.client.post('/api/auth/login/', {
            'email': 'admin@talentverify.com',
            'password': 'adminpass123'
        }, content_type='application/json')
        
        token = response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        # Should be able to access all companies
        response = self.client.get('/api/companies/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        companies = response.json()['results']
        self.assertEqual(len(companies), 2)  # Both companies
        
        # Should be able to access all employees
        response = self.client.get('/api/employees/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employees = response.json()['results']
        self.assertEqual(len(employees), 2)  # Both employees
        
        # Should be able to create employees
        response = self.client.post('/api/employees/', {
            'first_name': 'Admin',
            'last_name': 'Created',
            'employee_id_number': 'ADMIN001'
        }, content_type='application/json', **headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
