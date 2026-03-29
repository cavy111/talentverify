from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import auth_views, company_views, employee_views, search_views, bulk_upload_views

# Create DRF router
router = DefaultRouter()
router.register(r'companies', company_views.CompanyViewSet)
router.register(r'departments', company_views.DepartmentViewSet)
router.register(r'employees', employee_views.EmployeeViewSet)
router.register(r'employment-records', employee_views.EmploymentRecordViewSet)
router.register(r'role-duties', employee_views.RoleDutyViewSet)

app_name = 'core'

urlpatterns = [
    # Authentication endpoints
    path('auth/', include([
        path('login/', auth_views.login_view, name='login'),
        path('logout/', auth_views.logout_view, name='logout'),
        path('me/', auth_views.me_view, name='me'),
    ])),
    
    # Search endpoint
    path('search/', search_views.SearchView.as_view(), name='search'),
    
    # Bulk upload endpoint
    path('bulk-upload/', bulk_upload_views.BulkUploadView.as_view(), name='bulk_upload'),
    
    # API endpoints with ViewSets
    path('', include(router.urls)),
]
