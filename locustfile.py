from locust import HttpUser, task, between
import random
import json

class TalentVerifyUser(HttpUser):
    """Load testing user for Talent Verify platform"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    
    def on_start(self):
        """Called when a simulated user starts"""
        self.token = None
        self.login()
    
    def login(self):
        """Authenticate the user and store JWT token"""
        # Use test credentials - these should exist in your test database
        login_data = {
            "email": "admin@talentverify.com",
            "password": "admin123"
        }
        
        response = self.client.post("/api/auth/login/", json=login_data)
        
        if response.status_code == 200:
            response_data = response.json()
            self.token = response_data.get("access")
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
        else:
            # If login fails, try creating a test user first
            self.create_test_user()
    
    def create_test_user(self):
        """Create a test user if login fails"""
        # This assumes you have an endpoint to create test users
        # For now, we'll just continue without authentication
        pass
    
    @task(60)
    def search_task(self):
        """Search endpoint - highest frequency (60% weight)"""
        # Simulate different search queries
        search_params = [
            {"name": "John Doe"},
            {"employer": "Acme Corp"},
            {"position": "Software Engineer"},
            {"department": "Engineering"},
            {"year_started": "2020"},
            {"name": "Jane", "employer": "Tech Co"},
            {"position": "Manager", "department": "Sales"},
            {"year_started": "2019", "year_left": "2023"},
            {}  # Empty search to test endpoint
        ]
        
        params = random.choice(search_params)
        
        # Add random variation to simulate real usage patterns
        if random.random() < 0.1:  # 10% chance of complex search
            params.update({
                "name": f"Test User {random.randint(1, 100)}",
                "employer": f"Company {random.choice(['A', 'B', 'C'])}",
                "position": random.choice(["Engineer", "Manager", "Analyst", "Developer"])
            })
        
        self.client.get("/api/search/", params=params)
    
    @task(20)
    def login_task(self):
        """Login endpoint - medium frequency (20% weight)"""
        # Simulate different login attempts
        login_scenarios = [
            {"email": "admin@talentverify.com", "password": "admin123"},
            {"email": "test@company.com", "password": "testpass"},
            {"email": "user@example.com", "password": "wrongpass"},  # Failed login
            {"email": "admin@talentverify.com", "password": "admin123"},
        ]
        
        login_data = random.choice(login_scenarios)
        
        # Don't use stored token for this task - test fresh login
        headers = {}
        if not login_data["password"] == "wrongpass":
            # For successful logins, we might want to store the token
            response = self.client.post("/api/auth/login/", json=login_data, headers=headers)
            if response.status_code == 200:
                # Update stored token for other tasks
                response_data = response.json()
                self.token = response_data.get("access")
                self.client.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
        else:
            # Failed login - should trigger rate limiting eventually
            self.client.post("/api/auth/login/", json=login_data, headers=headers)
    
    @task(20)
    def employee_list_task(self):
        """Employee list endpoint - medium frequency (20% weight)"""
        if not self.token:
            # Try to login if we don't have a token
            self.login()
        
        if self.token:
            # Simulate different pagination and filtering
            page = random.randint(1, 5)  # Test different pages
            page_size = random.choice([10, 20, 50])  # Different page sizes
            
            params = {"page": page, "page_size": page_size}
            
            # Occasionally add search filters
            if random.random() < 0.3:  # 30% chance of filters
                filters = random.choice([
                    {"employee_id_number": f"EMP{random.randint(1, 999):03d}"},
                    {"search": random.choice(["John", "Jane", "Test"])},
                    {}
                ])
                params.update(filters)
            
            self.client.get("/api/employees/", params=params)
        else:
            # If still no token, try accessing without auth (should fail)
            self.client.get("/api/employees/")


class PublicSearchUser(HttpUser):
    """Simulates completely anonymous users doing public searches"""
    
    wait_time = between(0.5, 2)  # Faster wait time for public users
    
    @task
    def public_search_only(self):
        """Public users only do searches"""
        search_params = [
            {"name": "John"},
            {"employer": "Company"},
            {"position": "Engineer"},
            {"department": "Sales"},
            {"year_started": "2020"},
            {}
        ]
        
        params = random.choice(search_params)
        self.client.get("/api/search/", params=params)


class AuthenticatedUser(HttpUser):
    """Simulates authenticated users doing typical work"""
    
    wait_time = between(2, 5)  # Slower pace for authenticated users
    
    def on_start(self):
        """Login immediately for authenticated users"""
        self.token = None
        self.login()
    
    def login(self):
        """Login and store token"""
        login_data = {
            "email": "admin@talentverify.com",
            "password": "admin123"
        }
        
        response = self.client.post("/api/auth/login/", json=login_data)
        
        if response.status_code == 200:
            response_data = response.json()
            self.token = response_data.get("access")
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
    
    @task(3)
    def view_employees(self):
        """View employee list"""
        if self.token:
            page = random.randint(1, 3)
            self.client.get("/api/employees/", params={"page": page})
    
    @task(2)
    def view_employee_detail(self):
        """View specific employee details"""
        if self.token:
            # Try to view a few different employee IDs
            employee_ids = ["random-uuid-1", "random-uuid-2", "random-uuid-3"]
            employee_id = random.choice(employee_ids)
            self.client.get(f"/api/employees/{employee_id}/")
    
    @task(1)
    def search_employees(self):
        """Search within authenticated context"""
        if self.token:
            search_terms = ["John", "Jane", "Engineer", "Manager", "2020"]
            term = random.choice(search_terms)
            self.client.get("/api/search/", params={"name": term})
