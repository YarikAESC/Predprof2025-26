from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

def user_can_order(view_func):
    """Декоратор для проверки, может ли пользователь делать заказы"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Проверяем, есть ли у пользователя атрибут can_order
        if hasattr(request.user, 'can_order'):
            if not request.user.can_order():
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            # Или проверяем роль напрямую
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

class UserCanOrderMixin:
    """Миксин для классов представлений"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if hasattr(request.user, 'can_order'):
            if not request.user.can_order():
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        return super().dispatch(request, *args, **kwargs)
