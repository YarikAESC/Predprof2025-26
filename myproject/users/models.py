# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('student', 'Ученик'),
        ('chef', 'Повар'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    allergens = models.ManyToManyField(
        'orders.Ingredient',
        blank=True,
        verbose_name='Аллергены',
        help_text='Отметьте ингредиенты-аллергены'
    )
    
    # Поля баланса
    balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        verbose_name='Баланс'
    )
    bonus_points = models.IntegerField(
        default=0,
        verbose_name='Бонусные баллы'
    )
    
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser
    
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
    
    def can_afford(self, amount):
        #Проверка, хватает ли денег
        return self.balance >= amount
    
    def deduct_balance(self, amount, description=""):
        #Списание с баланса
        if self.can_afford(amount):
            self.balance -= amount
            self.save()
            
            # Импорт внутри метода, чтобы избежать круговой зависимости
            from orders.models import Transaction
            Transaction.objects.create(
                user=self,
                amount=-amount,
                balance_after=self.balance,
                description=description
            )
            return True
        return False
    
    def add_balance(self, amount, description=""):
        #Пополнение баланса
        self.balance += amount
        self.save()
        
        from orders.models import Transaction
        Transaction.objects.create(
            user=self,
            amount=amount,
            balance_after=self.balance,
            description=description
        )
        return True
