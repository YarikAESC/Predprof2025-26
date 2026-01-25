from django.contrib import admin

# Импорт для работы с пользователями
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import CustomUser
from django.utils.translation import gettext_lazy as _

# Форма для изменения пользователя
class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser

# Форма для создания пользователя
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email')

# Админка для кастомного пользователя
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    # Что показывать в списке
    list_display = ('username', 'email', 'first_name', 'last_name', 
                    'is_staff', 'is_active')
    # Фильтры справа
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'groups')
    # Поиск
    search_fields = ('username', 'email', 'first_name', 'last_name')
    # Сортировка
    ordering = ('-date_joined',)
    
    # Поля в форме редактирования
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': (
            'first_name', 'last_name', 'email',
            'phone', 'avatar', 'birth_date', 'allergens')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser',
                              'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Поля при создании нового пользователя
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2',
                      'first_name', 'last_name', 'phone'),
        }),
    )
    
    # Показ аватара в админке
    readonly_fields = ('avatar_preview',)
    
    # Функция для показа аватара
    def avatar_preview(self, obj):
        if obj.avatar:
            return f'<img src="{obj.avatar.url}" style="max-height: 100px;" />'
        return "Нет аватара"
    avatar_preview.allow_tags = True
    avatar_preview.short_description = 'Аватар'
