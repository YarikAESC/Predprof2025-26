from django.apps import AppConfig

# Настройки приложения заказы
class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # Стандартный ID поля
    name = 'orders'  # Название приложения
    verbose_name = 'Заказы'  # Имя в админке
