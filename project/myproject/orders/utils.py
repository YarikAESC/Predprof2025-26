from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

# Проверочная обёртка для функций представлений
def user_can_order(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Проверяем авторизован ли пользователь
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Проверяем может ли пользователь заказывать через метод can_order()
        if hasattr(request.user, 'can_order'):
            if not request.user.can_order():
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            # Проверяем по роли пользователя
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Класс для наследования с проверкой прав
class UserCanOrderMixin:
    def dispatch(self, request, *args, **kwargs):
        # Проверяем авторизован ли пользователь
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Проверяем может ли пользователь заказывать через метод can_order()
        if hasattr(request.user, 'can_order'):
            if not request.user.can_order():
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            # Проверяем по роли пользователя
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        return super().dispatch(request, *args, **kwargs)


# Проверка может ли пользователь использовать корзину
def user_can_use_cart(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Проверяем может ли пользователь использовать корзину
        if hasattr(request.user, 'can_have_cart'):
            if not request.user.can_have_cart():
                raise PermissionDenied("Корзина доступна только ученикам")
        else:
            # Проверяем по роли пользователя
            if not hasattr(request.user, 'role') or request.user.role != 'student':
                raise PermissionDenied("Корзина доступна только ученикам")

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# Класс для наследования с проверкой прав на корзину
class UserCanUseCartMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if hasattr(request.user, 'can_have_cart'):
            if not request.user.can_have_cart():
                raise PermissionDenied("Корзина доступна только ученикам")
        else:
            if not hasattr(request.user, 'role') or request.user.role != 'student':
                raise PermissionDenied("Корзина доступна только ученикам")

        return super().dispatch(request, *args, **kwargs)