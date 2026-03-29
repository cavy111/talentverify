from rest_framework import permissions


class IsTalentVerifyAdmin(permissions.BasePermission):
    """
    Allows access only if user.role == 'tv_admin'
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'tv_admin'
        )


class IsCompanyAdmin(permissions.BasePermission):
    """
    Allows access only if user.role == 'company_admin' and 
    user.company matches the resource's company
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'company_admin'
        )
    
    def has_object_permission(self, request, view, obj):
        # Check if the object has a company attribute
        if hasattr(obj, 'company'):
            return request.user.company == obj.company
        # Check if the object itself is a company
        elif hasattr(obj, 'id') and hasattr(request.user, 'company'):
            return obj == request.user.company
        return False


class IsCompanyUserOrAbove(permissions.BasePermission):
    """
    Allows any authenticated user whose company matches the resource
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.company is not None
        )
    
    def has_object_permission(self, request, view, obj):
        # Check if the object has a company attribute
        if hasattr(obj, 'company'):
            return request.user.company == obj.company
        # Check if the object itself is a company
        elif hasattr(obj, 'id') and hasattr(request.user, 'company'):
            return obj == request.user.company
        # Check if the object is an employee and belongs to the user's company
        elif hasattr(obj, 'employment_records'):
            return obj.employment_records.filter(
                company=request.user.company
            ).exists()
        return False
