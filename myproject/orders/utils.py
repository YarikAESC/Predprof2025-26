from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

# Проверка: может ли пользователь делать заказы
def user_can_order(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Проверяем, вошел ли пользователь в систему
        if not request.user.is_authenticated:
            return redirect('login')  # Если не вошел - на страницу входа
        
        # Проверяем, может ли пользователь заказывать
        if hasattr(request.user, 'can_order'):  # Если у пользователя есть метод can_order
            if not request.user.can_order():    # Если метод возвращает False
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            # Проверяем по роли (ученик или официант могут заказывать)
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        # Если все проверки пройдены - выполняем основную функцию
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# Класс для проверки прав на заказы (для классов-представлений)
class UserCanOrderMixin:
    def dispatch(self, request, *args, **kwargs):
        # Та же проверка, но для классов
        if not request.user.is_authenticated:
            return redirect('login')
        
        if hasattr(request.user, 'can_order'):
            if not request.user.can_order():
                raise PermissionDenied("У вас нет прав для оформления заказов")
        else:
            if not hasattr(request.user, 'role') or request.user.role not in ['customer', 'waiter']:
                raise PermissionDenied("У вас нет прав для оформления заказов")
        
        return super().dispatch(request, *args, **kwargs)


# Проверка: может ли пользователь использовать корзину
def user_can_use_cart(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Проверяем вход в систему
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Проверяем доступ к корзине
        if hasattr(request.user, 'can_have_cart'):  # Если есть специальный метод
            if not request.user.can_have_cart():    # И он возвращает False
                raise PermissionDenied("Корзина доступна только ученикам")
        else:
            # Проверяем по роли - только ученики могут иметь корзину
            if not hasattr(request.user, 'role') or request.user.role != 'student':
                raise PermissionDenied("Корзина доступна только ученикам")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


# Класс для проверки прав на корзину (для классов-представлений)
class UserCanUseCartMixin:
    def dispatch(self, request, *args, **kwargs):
        # Та же проверка для классов
        if not request.user.is_authenticated:
            return redirect('login')
        
        if hasattr(request.user, 'can_have_cart'):
            if not request.user.can_have_cart():
                raise PermissionDenied("Корзина доступна только ученикам")
        else:
            if not hasattr(request.user, 'role') or request.user.role != 'student':
                raise PermissionDenied("Корзина доступна только ученикам")
        
        return super().dispatch(request, *args, **kwargs)