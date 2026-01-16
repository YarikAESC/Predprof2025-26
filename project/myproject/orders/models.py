from django.db import models
from users.models import CustomUser

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Dish(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Категория')
    image = models.ImageField(upload_to='dishes/', blank=True, null=True, verbose_name='Изображение')
    is_available = models.BooleanField(default=True, verbose_name='Доступно')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    class Meta:
        verbose_name = 'Блюдо'
        verbose_name_plural = 'Блюда'
        ordering = ['category', 'name']
    
    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('confirmed', 'Подтвержден'),
        ('preparing', 'Готовится'),
        ('ready', 'Готово'),
        ('cancelled', 'Отменено'),
    ]
    
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, 
                                 related_name='orders', verbose_name='Ученик')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                              default='pending', verbose_name='Статус')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, 
                                      default=0, verbose_name='Общая сумма')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    is_visible_to_customer = models.BooleanField(default=True, verbose_name='Виден ученику')
    
    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Заказ #{self.id} от {self.customer.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name='Блюдо')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, 
                                        verbose_name='Цена на момент заказа')
    
    class Meta:
        verbose_name = 'Элемент заказа'
        verbose_name_plural = 'Элементы заказа'
    
    def __str__(self):
        return f"{self.dish.name} x {self.quantity}"
    
    def get_total(self):
        return self.price_at_time * self.quantity

