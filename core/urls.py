from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import auth_views, company_views

# Create DRF router
router = DefaultRouter()
router.register(r'companies', company_views.CompanyViewSet)
router.register(r'departments', company_views.DepartmentViewSet)

app_name = 'core'

urlpatterns = [
    # Authentication endpoints
    path('auth/', include([
        path('login/', auth_views.login_view, name='login'),
        path('logout/', auth_views.logout_view, name='logout'),
        path('me/', auth_views.me_view, name='me'),
    ])),
    
    # API endpoints with ViewSets
    path('', include(router.urls)),
]
