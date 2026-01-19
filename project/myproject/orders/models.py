# orders/models.py
from django.db import models
from users.models import CustomUser


# МОДЕЛЬ КАТЕГОРИЙ БЛЮД

# Хранит категории для группировки блюд (например, супы, салаты, горячее)
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']
    
    def __str__(self):
        return self.name


# МОДЕЛЬ БЛЮД

# Основная модель для хранения информации о блюдах в меню
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


# МОДЕЛЬ ЗАКАЗОВ

# Основная модель для хранения заказов пользователей
class Order(models.Model):
    # Варианты статусов заказа
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('confirmed', 'Подтвержден'),
        ('preparing', 'Готовится'),
        ('ready', 'Готово'),
        ('delivered', 'Забран'),
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


# МОДЕЛЬ ЭЛЕМЕНТОВ ЗАКАЗА

# Хранит отдельные позиции в заказе (связь многие-ко-многим между Order и Dish)
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
    
    # Расчет стоимости позиции
    def get_total(self):
        return self.price_at_time * self.quantity


# МОДЕЛЬ ОТМЕТКИ ПОЛУЧЕНИЯ ЗАКАЗА

# Фиксирует факт получения заказа пользователем
class OrderPickup(models.Model):
    order = models.OneToOneField('Order', on_delete=models.CASCADE, related_name='pickup')
    picked_up_at = models.DateTimeField(auto_now_add=True)
    picked_up_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Получение заказа'
        verbose_name_plural = 'Получения заказов'
    
    def __str__(self):
        return f"Заказ #{self.order.id} получен"


# МОДЕЛЬ ПЛАТЕЖЕЙ

# Хранит информацию об оплатах заказов
class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('failed', 'Ошибка оплаты'),
    ]
    
    PAYMENT_METHOD = [
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('bonus', 'Бонусы'),
    ]
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='cash')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'
    
    def __str__(self):
        return f"Платеж #{self.id} - {self.amount} руб."


# МОДЕЛЬ ТРАНЗАКЦИЙ (ИСТОРИЯ ОПЕРАЦИЙ С БАЛАНСОМ)

# Хранит историю всех операций с балансом пользователя
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Пополнение'),
        ('payment', 'Оплата заказа'),
        ('refund', 'Возврат'),
        ('bonus', 'Бонусы'),
    ]
    
    # Строковая ссылка для избежания циклического импорта
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='payment')
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()}: {self.amount} руб."
