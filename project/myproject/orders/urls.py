from django.urls import path
from . import views

urlpatterns = [
    # Основные URL для меню и корзины
    path('', views.MenuView.as_view(), name='menu'),  # Главная страница с меню
    path('cart/', views.view_cart, name='view_cart'),  # Страница корзины
    path('cart/add/<int:dish_id>/', views.add_to_cart, name='add_to_cart'),  # Добавить в корзину
    path('cart/update/<int:dish_id>/', views.update_cart, name='update_cart'),  # Обновить корзину
    path('cart/remove/<int:dish_id>/', views.remove_from_cart, name='remove_from_cart'),  # Удалить из корзины
    
    # URL для работы с заказами
    path('order/create/', views.create_order, name='create_order'),  # Создать заказ
    path('orders/', views.my_orders, name='my_orders'),  # Мои заказы
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),  # Детали заказа
    path('order/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),  # Отменить заказ
    path('order/<int:order_id>/update_status/', views.update_order_status, name='update_order_status'),  # Изменить статус заказа
    path('order/hide/<int:order_id>/', views.hide_order, name='hide_order'),  # Скрыть/забрать заказ
    
    # URL для администратора
    path('manage/dashboard/', views.admin_dashboard, name='admin_dashboard'),  # Админ панель
    path('manage/dishes/', views.manage_dishes, name='manage_dishes'),  # Управление блюдами
    path('manage/users/', views.manage_users, name='manage_users'),  # Управление пользователями
    path('manage/users/<int:user_id>/change_role/', views.change_user_role, name='change_user_role'),  # Изменить роль пользователя
    
    # URL для повара
    path('chef/orders/', views.chef_orders, name='chef_orders'),  # Заказы для повара
]
