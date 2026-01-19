from django.contrib.auth.models import AbstractUser
from django.db import models

# Пользовательская модель пользователя
class CustomUser(AbstractUser):
    # Варианты ролей
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('student', 'Ученик'),
        ('chef', 'Повар'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')  # Роль
    phone = models.CharField(max_length=15, blank=True)  # Телефон
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)  # Фото
    birth_date = models.DateField(blank=True, null=True)  # Дата рождения
    
    # Проверка является ли администратором
    def is_admin(self):
        return self.role == 'admin'
    
    # Проверка является ли учеником
    def is_student(self):
        return self.role == 'student'
    
    # Проверка является ли поваром
    def is_chef(self):
        return self.role == 'chef'
    
    # Проверка может ли смотреть все заказы
    def can_view_all_orders(self):
        return self.role in ['admin', 'chef']
    
    # Проверка может ли менять статус заказа
    def can_change_order_status(self):
        return self.role in ['admin', 'chef']
    
    # Проверка может ли делать заказы
    def can_order_dishes(self):
        return self.role in ['student']

    # Проверка может ли иметь корзину
    def can_have_cart(self):
        return self.role == 'student'