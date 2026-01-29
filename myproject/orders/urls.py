from django.urls import path
from . import views

urlpatterns = [
    # Главная страница сайта
    path('', views.home, name='home'),
    path('add_allergen/', views.add_allergen, name='add_allergen'),
    path('remove_allergen/<int:allergen_id>/', views.remove_allergen, name='remove_allergen'),
    #  Меню и корзина 
    # Страница меню (только ученики)
    path('menu/', views.MenuView.as_view(), name='menu'),
    
    # Управление корзиной
    path('cart/', views.view_cart, name='view_cart'),  # Просмотр корзины
    path('cart/add/<int:dish_id>/', views.add_to_cart, name='add_to_cart'),  # Добавить блюдо в корзину
    path('cart/update/<int:dish_id>/', views.update_cart, name='update_cart'),  # Изменить количество
    path('cart/remove/<int:dish_id>/', views.remove_from_cart, name='remove_from_cart'),  # Удалить из корзины
    
    #  Комбо-наборы 
    # Главная страница комбо-наборов
    path('combo/', views.my_combo, name='my_combo'),
    # Создание набора
    path('combo/create/', views.create_combo_set, name='create_combo_set'),
    # Мои наборы
    path('combo/list/', views.my_combo_sets, name='my_combo_sets'),
    # Заказ набора
    path('combo/<int:combo_id>/order/', views.order_combo_set, name='order_combo_set'),
    # Заказы комбо-наборов
    path('combo/orders/', views.my_combo_orders, name='my_combo_orders'),
    # Отмена заказа набора
    path('combo/<int:order_id>/cancel/', views.cancel_combo_order, name='cancel_combo_order'),
    # Заказы комбо-наборов для повара
    path('chef/combo-orders/', views.chef_combo_orders, name='chef_combo_orders'),
    # Изменение статуса заказа набора (повар)
    path('chef/combo-order/<int:order_id>/update/', views.update_combo_order_status, name='update_combo_order_status'),
    
    #  Баланс и оплата 
    # Мой баланс
    path('balance/', views.my_balance, name='my_balance'),
    # Пополнение баланса
    path('balance/add/', views.add_balance, name='add_balance'),
    # Оплата заказа с баланса
    path('order/<int:order_id>/pay-balance/', views.pay_with_balance, name='pay_with_balance'),
    
    #  Заказы 
    # Создание заказа
    path('order/create/', views.create_order, name='create_order'),
    # Мои активные заказы
    path('orders/', views.my_orders, name='my_orders'),
    # История заказов
    path('order-history/', views.order_history, name='order_history'),
    # Детали заказа
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    # Отмена заказа
    path('order/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),
    # Изменение статуса заказа
    path('order/<int:order_id>/update_status/', views.update_order_status, name='update_order_status'),
    # Отметка получения заказа
    path('order/<int:order_id>/pick/', views.mark_as_picked, name='mark_picked'),
    
    #  Отзывы 
    # Добавление отзыва на блюдо
    path('add-review/<int:order_id>/<int:dish_id>/', views.add_review, name='add_review'),
    
    #  Администратор 
    # Главная страница админа
    path('manage/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # Управление заказами
    path('manage/orders/', views.manage_orders, name='manage_orders'),
    # Управление блюдами
    path('manage/dishes/', views.manage_dishes, name='manage_dishes'),
    # Добавление нового блюда
    path('manage/dishes/add/', views.add_dish, name='add_dish'),
    # Редактирование блюда
    path('manage/dishes/<int:dish_id>/update-image/', views.update_dish_image, name='update_dish_image'),
    path('manage/dishes/edit/<int:dish_id>/', views.edit_dish, name='edit_dish'),
    # Управление пользователями
    path('manage/users/', views.manage_users, name='manage_users'),
    # Изменение роли пользователя
    path('manage/users/<int:user_id>/change_role/', views.change_user_role, name='change_user_role'),
    
    #  Ингредиенты 
    # Добавление ингредиента
    path('manage/ingredients/add/', views.add_ingredient, name='add_ingredient'),
    
    #  Статистика 
    # Отметка оплаты заказа (админ)
    path('order/<int:order_id>/pay/', views.mark_as_paid, name='mark_paid'),
    # Статистика (админ)
    path('statistics/', views.statistics, name='statistics'),
    
    #  Повар 
    # Заказы для повара
    path('chef/orders/', views.chef_orders, name='chef_orders'),
    
    #  Управление запасами
    # Выполнение запроса на пополнение
    path('manage/inventory/request/<int:request_id>/fulfill/', 
     views.fulfill_restock_request, name='fulfill_restock_request'),
    # Обновление стоимости ингредиента
    path('manage/ingredient/<int:ingredient_id>/update-cost/', 
     views.update_ingredient_cost, name='update_ingredient_cost'),
    # Запасы ингредиентов для повара
    path('chef/inventory/', views.chef_inventory, name='chef_inventory'),
    # Запрос на пополнение
    path('chef/inventory/<int:ingredient_id>/request-restock/', 
         views.request_restock, name='request_restock'),
    # Приготовление блюд поваром
    path('chef/prepare-dishes/', views.chef_prepare_dishes, name='chef_prepare_dishes'),
    
    # Управление запасами для админа
    path('manage/inventory/', views.manage_inventory, name='manage_inventory'),
    # Пополнение запаса
    path('manage/inventory/<int:stock_id>/restock/', 
         views.restock_ingredient, name='restock_ingredient'),
    # Корректировка запаса
    path('manage/inventory/<int:stock_id>/adjust/', 
         views.adjust_stock, name='adjust_stock'),
    # Удаление запроса на пополнение
    path('manage/inventory/request/<int:request_id>/delete/',
         views.delete_restock_request, name='delete_restock_request'),
]
