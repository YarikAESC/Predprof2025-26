# Настройки Django для проекта myproject
import os
from pathlib import Path

# Базовый путь проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Секретный ключ для безопасности - НЕ ПОКАЗЫВАТЬ В ПРОД!
SECRET_KEY = 'django-insecure-bk%$u45-4nu73rq6qdewkt79fxj=mmq*4ii0ulled+9==54v24'

# Режим отладки - True для разработки
DEBUG = True

# Список разрешенных хостов
ALLOWED_HOSTS = []

# Установленные приложения
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'orders',  # Приложение заказов
    'users',   # Приложение пользователей
]

# Промежуточные слои (middleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Главный файл URL-адресов
ROOT_URLCONF = 'myproject.urls'

# Настройки шаблонов
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),  # Папка с шаблонами проекта
        ],
        'APP_DIRS': True,  # Искать шаблоны в приложениях
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',  # Для медиафайлов
            ],
        },
    },
]

# WSGI приложение
WSGI_APPLICATION = 'myproject.wsgi.application'

# Настройки базы данных
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # Используем SQLite
        'NAME': BASE_DIR / 'db.sqlite3',  # Файл базы данных
    }
}

# Валидаторы паролей
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Используем кастомную модель пользователя
AUTH_USER_MODEL = 'users.CustomUser'

# Настройки интернационализации
LANGUAGE_CODE = 'ru-RU'  # Русский язык
TIME_ZONE = 'Europe/Moscow'  # Московское время
USE_I18N = True
USE_TZ = True

# Настройки статических файлов
STATIC_URL = 'static/'  # URL для статических файлов
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')  # Папка со статическими файлами
]

# Настройки медиа файлов (загружаемые пользователем)
MEDIA_URL = '/media/'  # URL для медиа файлов
MEDIA_ROOT = BASE_DIR / 'media'  # Папка для медиа файлов

# Поле по умолчанию для первичного ключа
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Папка для статических файлов в продакшене
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Настройки авторизации
LOGIN_REDIRECT_URL = '/users/'  # Куда идти после входа
LOGOUT_REDIRECT_URL = '/users/login/'  # Куда идти после выхода
LOGIN_URL = '/users/login/'  # Куда отправлять для входа
