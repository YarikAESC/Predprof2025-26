from django.db import models
from users.models import CustomUser
from django.conf import settings
from decimal import Decimal


# КАТЕГОРИИ БЛЮД - для группировки (супы, салаты, горячее)
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']
    
    def __str__(self):
        return self.name


# ИНГРЕДИЕНТЫ - продукты для приготовления блюд
class Ingredient(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    unit = models.CharField(max_length=20, verbose_name='Единица измерения')  # г, мл, шт

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ['name']

    def __str__(self):
        return self.name


# ЗАПАСЫ ИНГРЕДИЕНТОВ НА СКЛАДЕ
class IngredientStock(models.Model):
    ingredient = models.OneToOneField(Ingredient, on_delete=models.CASCADE, 
                                      related_name='stock', verbose_name='Ингредиент')
    current_quantity = models.DecimalField(max_digits=10, decimal_places=2, 
                                           default=0, verbose_name='Текущее количество')
    min_quantity = models.DecimalField(max_digits=10, decimal_places=2, 
                                       default=10, verbose_name='Минимальное количество')
    unit = models.CharField(max_length=20, verbose_name='Единица измерения')
    last_restocked = models.DateTimeField(auto_now=True, verbose_name='Последнее пополнение')
    
    class Meta:
        verbose_name = 'Запас ингредиента'
        verbose_name_plural = 'Запасы ингредиентов'
        ordering = ['ingredient__name']
    
    def __str__(self):
        return f"{self.ingredient.name}: {self.current_quantity} {self.unit}"
    
    @property
    def is_low(self):
        #Проверяет, мало ли осталось ингредиента
        return self.current_quantity <= self.min_quantity
    
    @property
    def is_out_of_stock(self):
        #Проверяет, закончился ли ингредиент
        return self.current_quantity <= 0


# ИСТОРИЯ ИЗМЕНЕНИЙ ЗАПАСОВ
class StockHistory(models.Model):
    # Типы операций
    OPERATION_TYPES = [
        ('restock', 'Пополнение'),
        ('usage', 'Использование'),
        ('adjustment', 'Корректировка'),
        ('waste', 'Списание (брак)'),
        ('request', 'Запрос на пополнение'),
    ]
    
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, 
                                   related_name='stock_history')
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES)
    quantity_change = models.DecimalField(max_digits=10, decimal_places=2, 
                                          verbose_name='Изменение количества')
    quantity_before = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_after = models.DecimalField(max_digits=10, decimal_places=2)
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, 
                                     null=True, verbose_name='Кто выполнил')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата операции')
    
    class Meta:
        verbose_name = 'История запасов'
        verbose_name_plural = 'История запасов'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_operation_type_display()}: {self.ingredient.name} ({self.quantity_change})"


# БЛЮДА - вся информация о позициях в меню
class Dish(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Категория')
    image = models.ImageField(upload_to='dishes/', blank=True, null=True, verbose_name='Изображение')
    is_available = models.BooleanField(default=True, verbose_name='Доступно')
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    
    # Получить все ингредиенты блюда
    @property
    def ingredients_list(self):
        return self.ingredients.select_related('ingredient')
    
    class Meta:
        verbose_name = 'Блюдо'
        verbose_name_plural = 'Блюда'
        ordering = ['category', 'name']
    
    def __str__(self):
        return self.name

    # Средняя оценка блюда из отзывов
    @property
    def average_rating(self):
        from django.db.models import Avg
        result = self.reviews.aggregate(Avg('rating'))
        return result['rating__avg'] or 0

    def check_availability(self, quantity=1):
        # Проверяет, можно ли приготовить указанное количество этого блюда
        # Возвращает (доступно, недостающие_ингредиенты)
        unavailable_ingredients = []
        
        for dish_ingredient in self.ingredients.all():
            required = dish_ingredient.quantity * quantity
            try:
                stock = dish_ingredient.ingredient.stock
                if stock.current_quantity < required:
                    unavailable_ingredients.append({
                        'ingredient': dish_ingredient.ingredient,
                        'required': required,
                        'available': stock.current_quantity,
                        'missing': required - stock.current_quantity
                    })
            except IngredientStock.DoesNotExist:
                unavailable_ingredients.append({
                    'ingredient': dish_ingredient.ingredient,
                    'required': required,
                    'available': 0,
                    'missing': required
                })
        
        return len(unavailable_ingredients) == 0, unavailable_ingredients
    
    def reserve_ingredients(self, quantity=1, user=None):
        # Резервирует ингредиенты для приготовления блюда
        # Возвращает True если успешно, False если недостаточно
        is_available, missing = self.check_availability(quantity)
        
        if not is_available:
            return False, missing
        
        # Резервируем ингредиенты
        for dish_ingredient in self.ingredients.all():
            required = dish_ingredient.quantity * quantity
            stock = dish_ingredient.ingredient.stock
            stock.current_quantity -= required
            stock.save()
            
            # Записываем в историю
            StockHistory.objects.create(
                ingredient=dish_ingredient.ingredient,
                operation_type='usage',
                quantity_change=-required,
                quantity_before=stock.current_quantity + required,
                quantity_after=stock.current_quantity,
                performed_by=user,
                notes=f"Использовано для приготовления {self.name} x{quantity}"
            )
        
        return True, []

    def get_max_available_quantity(self):
        # Возвращает максимальное количество этого блюда, которое можно заказать 
        max_available = 0
        
        # Готовые блюда
        prepared_dishes = PreparedDish.objects.filter(dish=self)
        prepared_available = sum(pd.quantity for pd in prepared_dishes)
        max_available += prepared_available
        
        # Уже есть
        try:
            prepared_dishes = PreparedDish.objects.filter(dish=self)
            total_available = sum(pd.quantity for pd in prepared_dishes)
            return total_available
        except:
            return 0
    

# ИНГРЕДИЕНТЫ В БЛЮДЕ - сколько и каких ингредиентов в каждом блюде
class DishIngredient(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='ingredients')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Количество')

    class Meta:
        verbose_name = 'Ингредиент блюда'
        verbose_name_plural = 'Ингредиенты блюда'
        # Один ингредиент не может повторяться в одном блюде
        unique_together = ('dish', 'ingredient')

    def __str__(self):
        return f"{self.ingredient.name} — {self.quantity} {self.ingredient.unit} ({self.dish.name})"


# БЛЮДА ГОТОВЫЕ К ВЫДАЧЕ
class PreparedDish(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, 
                             related_name='prepared_items', verbose_name='Блюдо')
    quantity = models.PositiveIntegerField(default=0, verbose_name='Количество готовых')
    max_quantity = models.PositiveIntegerField(default=20, verbose_name='Максимальное количество')
    prepared_at = models.DateTimeField(auto_now_add=True, verbose_name='Время приготовления')
    prepared_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, 
                                    null=True, verbose_name='Кто приготовил')
    
    class Meta:
        verbose_name = 'Готовое блюдо'
        verbose_name_plural = 'Готовые блюда'
        ordering = ['dish__name']
    
    def __str__(self):
        return f"{self.dish.name}: {self.quantity} шт."
    
    @property
    def is_available(self):
        return self.quantity > 0
    
    @property
    def needs_preparation(self):
        return self.quantity < self.max_quantity / 2


# ЗАКАЗЫ - основной заказ пользователя
class Order(models.Model):
    # Варианты статусов заказа
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('confirmed', 'Подтвержден'),
        ('preparing', 'Готовится'),
        ('ready', 'Готово'),
        ('picked_up', 'Получен'),
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


# ЭЛЕМЕНТЫ ЗАКАЗА - отдельные блюда в заказе
class OrderItem(models.Model):
    # Статусы элемента заказа
    ITEM_STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('preparing', 'Готовится'),
        ('ready', 'Готово'),
        ('out_of_stock', 'Нет в наличии'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name='Блюдо')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, 
                                        verbose_name='Цена на момент заказа')
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, 
                              default='pending', verbose_name='Статус')
    
    class Meta:
        verbose_name = 'Элемент заказа'
        verbose_name_plural = 'Элементы заказа'
    
    def __str__(self):
        return f"{self.dish.name} x {self.quantity}"
    
    # Сколько стоит эта позиция
    def get_total(self):
        return self.price_at_time * self.quantity


# ПОЛУЧЕНИЕ ЗАКАЗА - когда ученик забрал свой заказ
class OrderPickup(models.Model):
    order = models.OneToOneField('Order', on_delete=models.CASCADE, related_name='pickup')
    picked_up_at = models.DateTimeField(auto_now_add=True)
    picked_up_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Получение заказа'
        verbose_name_plural = 'Получения заказов'
    
    def __str__(self):
        return f"Заказ #{self.order.id} получен"


# ПЛАТЕЖИ - информация об оплате
class Payment(models.Model):
    # Статусы платежа
    PAYMENT_STATUS = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('failed', 'Ошибка оплаты'),
    ]
    
    # Способы оплаты
    PAYMENT_METHOD = [
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('bonus', 'Бонусы'),
    ]
    
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='payments', 
                             null=True, blank=True, verbose_name='Заказ')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='cash')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, verbose_name='Описание платежа')
    
    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'
    
    def __str__(self):
        return f"Платеж #{self.id} - {self.amount} руб."


# ТРАНЗАКЦИИ - история операций с балансом
class Transaction(models.Model):
    # Типы операций
    TRANSACTION_TYPES = [
        ('deposit', 'Пополнение'),
        ('payment', 'Оплата заказа'),
        ('refund', 'Возврат'),
        ('bonus', 'Бонусы'),
    ]
    
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


# ОТЗЫВЫ - оценки и комментарии к блюдам
class Review(models.Model):
    # Варианты оценок от 1 до 5 звезд
    RATING_CHOICES = [
        (1, '★☆☆☆☆ - Ужасно'),
        (2, '★★☆☆☆ - Плохо'),
        (3, '★★★☆☆ - Нормально'),
        (4, '★★★★☆ - Хорошо'),
        (5, '★★★★★ - Отлично'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='reviews'
    )

    dish = models.ForeignKey(
        'Dish',
        on_delete=models.CASCADE,
        verbose_name='Блюдо',
        related_name='reviews'
    )

    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        verbose_name='Заказ',
        related_name='reviews',
        null=True,
        blank=True
    )

    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        verbose_name='Оценка',
        default=5
    )

    comment = models.TextField(
        verbose_name='Комментарий',
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']
        # Один пользователь не может оставлять несколько отзывов на одно блюдо в одном заказе
        unique_together = ['user', 'dish', 'order']

    def __str__(self):
        return f'Отзыв от {self.user.username} на {self.dish.name} ({self.rating}/5)'


# КОМБО-НАБОР - готовый набор блюд
class ComboSet(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название набора')
    description = models.TextField(blank=True, verbose_name='Описание')
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                                   related_name='combo_sets', verbose_name='Создатель')
    total_price = models.DecimalField(max_digits=10, decimal_places=2,
                                      verbose_name='Цена за один набор')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    max_orders = models.PositiveIntegerField(default=1, verbose_name='Максимальное количество заказов',
                                             help_text='Сколько раз можно заказать этот набор')
    orders_used = models.PositiveIntegerField(default=0, verbose_name='Использовано заказов',
                                              editable=False)

    class Meta:
        verbose_name = 'Комбо-набор'
        verbose_name_plural = 'Комбо-наборы'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (создал: {self.created_by.username})"

    # Сколько раз еще можно заказать этот набор
    @property
    def remaining_orders(self):
        return max(0, self.max_orders - self.orders_used)

    # Доступен ли набор для заказа сейчас
    @property
    def is_available(self):
        return self.is_active and self.remaining_orders > 0

    # Увеличить счетчик использования на 1
    def increment_usage(self):
        self.orders_used += 1
        if self.orders_used >= self.max_orders:
            self.is_active = False
        self.save(update_fields=['orders_used', 'is_active'])

    # Общая сумма, заплаченная за весь набор (цена × количество заказов)
    @property
    def total_paid(self):
        return self.total_price * self.max_orders


# ЭЛЕМЕНТ КОМБО-НАБОРА - одно блюдо в наборе
class ComboItem(models.Model):
    combo_set = models.ForeignKey(ComboSet, on_delete=models.CASCADE,
                                  related_name='items', verbose_name='Набор')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name='Блюдо')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')

    class Meta:
        verbose_name = 'Элемент комбо-набора'
        verbose_name_plural = 'Элементы комбо-наборов'

    def __str__(self):
        return f"{self.dish.name} x{self.quantity}"


# ЗАКАЗ КОМБО-НАБОРА - когда ученик заказывает готовый набор
class ComboOrder(models.Model):
    # Статусы заказа набора
    STATUS_CHOICES = [
        ('preparing', 'Готовится'),
        ('ready', 'Готово'),
        ('picked_up', 'Получен'),
    ]

    combo_set = models.ForeignKey(ComboSet, on_delete=models.CASCADE,
                                  related_name='orders', verbose_name='Набор')
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                                 related_name='combo_orders', verbose_name='Ученик')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='preparing', verbose_name='Статус')
    main_order = models.ForeignKey('Order', on_delete=models.SET_NULL, 
                                   null=True, blank=True, related_name='combo_order_ref',
                                   verbose_name='Основной заказ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Заказ комбо-набора'
        verbose_name_plural = 'Заказы комбо-наборов'
        ordering = ['-created_at']

    def __str__(self):
        return f"Заказ набора #{self.combo_set.id} от {self.customer.username}"

    # Цена заказа (равна цене набора)
    @property
    def total_price(self):
        return self.combo_set.total_price
# СТОИМОСТЬ ИНГРЕДИЕНТА
class IngredientCost(models.Model):
    ingredient = models.OneToOneField(Ingredient, on_delete=models.CASCADE, 
                                      related_name='cost', verbose_name='Ингредиент')
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, 
                                        default=0, verbose_name='Стоимость за единицу (руб)')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Последнее обновление')
    
    class Meta:
        verbose_name = 'Стоимость ингредиента'
        verbose_name_plural = 'Стоимость ингредиентов'
    
    def __str__(self):
        return f"{self.ingredient.name}: {self.cost_per_unit} руб/{self.ingredient.unit}"
    
    def calculate_total_cost(self, quantity):
        #Рассчитывает общую стоимость для указанного количества
        return self.cost_per_unit * quantity

class StockHistory(models.Model):
    # Типы операций
    OPERATION_TYPES = [
        ('restock', 'Пополнение'),
        ('usage', 'Использование'),
        ('adjustment', 'Корректировка'),
        ('waste', 'Списание (брак)'),
        ('request', 'Запрос на пополнение'),
    ]
    
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, 
                                   related_name='stock_history')
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES)
    quantity_change = models.DecimalField(max_digits=10, decimal_places=2, 
                                          verbose_name='Изменение количества')
    quantity_before = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_after = models.DecimalField(max_digits=10, decimal_places=2)
    # Добавляем поле для стоимости
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='Общая стоимость операции')
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, 
                                     null=True, verbose_name='Кто выполнил')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата операции')
    
    class Meta:
        verbose_name = 'История запасов'
        verbose_name_plural = 'История запасов'
        ordering = ['-created_at']
