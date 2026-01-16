# Настройка ASGI для проекта myproject

import os

from django.core.asgi import get_asgi_application

# Устанавливаем настройки проекта
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Создаем ASGI приложение
application = get_asgi_application()
