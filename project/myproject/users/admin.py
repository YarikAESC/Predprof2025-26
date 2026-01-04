from django.contrib import admin

# Register your models here.
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import CustomUser
from django.utils.translation import gettext_lazy as _

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email')

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    # Отображение в списке
    list_display = ('username', 'email', 'first_name', 'last_name', 
                    'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'groups')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    # Поля в форме редактирования
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 
                                        'phone', 'avatar', 'birth_date')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                      'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    # Поля при создании пользователя
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2',
                      'first_name', 'last_name', 'phone'),
        }),
    )
    
    # Для отображения аватара в админке
    readonly_fields = ('avatar_preview',)
    
    def avatar_preview(self, obj):
        if obj.avatar:
            return f'<img src="{obj.avatar.url}" style="max-height: 100px;" />'
        return "Нет аватара"
    avatar_preview.allow_tags = True
    avatar_preview.short_description = 'Предпросмотр аватара'
