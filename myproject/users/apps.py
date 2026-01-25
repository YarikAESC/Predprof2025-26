from django.apps import AppConfig

# Конфигурация приложения users
class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # Стандартное поле ID
    name = 'users'  # Название приложения
