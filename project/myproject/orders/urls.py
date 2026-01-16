from django.urls import path
from . import views

urlpatterns = [
    path('', views.MenuView.as_view(), name='menu'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:dish_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:dish_id>/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:dish_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('order/create/', views.create_order, name='create_order'),
    path('orders/', views.my_orders, name='my_orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('order/<int:order_id>/update_status/', views.update_order_status, name='update_order_status'),
    path('order/hide/<int:order_id>/', views.hide_order, name='hide_order'),
    
    # Админские URL
    path('manage/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('manage/dishes/', views.manage_dishes, name='manage_dishes'),
    path('manage/users/', views.manage_users, name='manage_users'),
    path('manage/users/<int:user_id>/change_role/', views.change_user_role, name='change_user_role'),
    
    # Для повара
    path('chef/orders/', views.chef_orders, name='chef_orders'),
]

