from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Список URL-адресов проекта
urlpatterns = [
    path('', include('orders.urls')),  # Главная страница - приложение orders
    path('admin/', admin.site.urls),   # Админка Django
    path('users/', include('users.urls')),  # Приложение пользователей
]

# Добавляем обработку файлов в режиме разработки
if settings.DEBUG:
    # Отдаем файлы из папки media
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Отдаем статические файлы
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
