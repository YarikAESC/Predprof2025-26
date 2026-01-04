from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('student', 'Ученик'),
        ('chef', 'Повар'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True)  # Добавить
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)  # Добавить
    birth_date = models.DateField(blank=True, null=True)  # Добавить
    def is_admin(self):
        return self.role == 'admin'
    
    def is_student(self):
        return self.role == 'student'
    
    def is_chef(self):
        return self.role == 'chef'
    
    def can_view_all_orders(self):
        return self.role in ['admin', 'chef']
    
    def can_change_order_status(self):
        return self.role in ['admin', 'chef']
    
    def can_order_dishes(self):
        return self.role in ['student', 'admin']
