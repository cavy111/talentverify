from django.urls import path
from core.views import auth_views

app_name = 'core'

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', auth_views.login_view, name='login'),
    path('auth/logout/', auth_views.logout_view, name='logout'),
    path('auth/me/', auth_views.me_view, name='me'),
]
