from django.contrib import admin
from django.db.models import F
from .models import Category, Dish, Order, OrderItem, Ingredient, DishIngredient, ComboSet, ComboItem, ComboOrder, Payment, IngredientStock, StockHistory, PreparedDish

#  КАТЕГОРИИ 
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Категории блюд
    list_display = ['name', 'description']  # Что показывать в списке
    search_fields = ['name']  # Поиск по названию

#  ИНГРЕДИЕНТЫ В БЛЮДЕ 
class DishIngredientInline(admin.TabularInline):
    # Ингредиенты прямо в форме блюда
    model = DishIngredient
    extra = 1  # Показать 1 пустое поле для добавления

#  БЛЮДА 
@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    # Управление блюдами
    list_display = ['name', 'category', 'price', 'is_available']  # Столбцы в таблице
    list_filter = ['category', 'is_available']  # Фильтры справа
    search_fields = ['name', 'description']  # Поиск по названию и описанию
    list_editable = ['price', 'is_available']  # Можно менять прямо в таблице
    inlines = [DishIngredientInline]  # Добавить ингредиенты в ту же форму
    
    def save_model(self, request, obj, form, change):
        # При создании нового блюда записать кто его создал
        if not obj.pk:  # Если блюдо еще не сохранено в базе
            obj.created_by = request.user  # Указываем текущего пользователя
        super().save_model(request, obj, form, change)

#  ЭЛЕМЕНТЫ ЗАКАЗА 
class OrderItemInline(admin.TabularInline):
    # Блюда в заказе
    model = OrderItem
    extra = 0  # Не показывать пустые поля

#  ЗАКАЗЫ 
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Управление заказами
    list_display = ['id', 'customer', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']  # Фильтр по статусу и дате
    search_fields = ['customer__username', 'customer__email']  # Поиск по ученику
    inlines = [OrderItemInline]  # Показать блюда заказа
    readonly_fields = ['created_at', 'updated_at']  # Эти поля нельзя менять

#  ИНГРЕДИЕНТЫ 
@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    # Управление ингредиентами
    list_display = ['name', 'unit']  # Название и единица измерения
    search_fields = ['name']  # Поиск по названию

# Кастомный фильтр для IngredientStock
class IsLowFilter(admin.SimpleListFilter):
    title = 'Мало осталось'
    parameter_name = 'is_low'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да (мало)'),
            ('no', 'Нет (достаточно)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(current_quantity__lte=F('min_quantity'))
        if self.value() == 'no':
            return queryset.filter(current_quantity__gt=F('min_quantity'))

# Кастомный фильтр для доступности ингредиента
class IsOutOfStockFilter(admin.SimpleListFilter):
    title = 'Закончился'
    parameter_name = 'is_out'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да (закончился)'),
            ('no', 'Нет (есть в наличии)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(current_quantity__lte=0)
        if self.value() == 'no':
            return queryset.filter(current_quantity__gt=0)

#  ЗАПАСЫ ИНГРЕДИЕНТОВ 
@admin.register(IngredientStock)
class IngredientStockAdmin(admin.ModelAdmin):
    # Управление запасами ингредиентов
    list_display = ['ingredient', 'current_quantity', 'unit', 'min_quantity', 'is_low_display', 'is_out_of_stock_display', 'last_restocked']
    list_filter = [IsLowFilter, IsOutOfStockFilter, 'last_restocked']
    search_fields = ['ingredient__name']
    list_editable = ['current_quantity', 'min_quantity']
    
    def is_low_display(self, obj):
        return obj.is_low
    is_low_display.short_description = 'Мало осталось'
    is_low_display.boolean = True
    
    def is_out_of_stock_display(self, obj):
        return obj.is_out_of_stock
    is_out_of_stock_display.short_description = 'Закончился'
    is_out_of_stock_display.boolean = True

#  ИСТОРИЯ ЗАПАСОВ 
@admin.register(StockHistory)
class StockHistoryAdmin(admin.ModelAdmin):
    # История изменений запасов
    list_display = ['ingredient', 'operation_type', 'quantity_change', 'quantity_before', 'quantity_after', 'performed_by', 'created_at']
    list_filter = ['operation_type', 'created_at']
    search_fields = ['ingredient__name', 'notes']
    readonly_fields = ['created_at']

# Кастомный фильтр для доступности готовых блюд
class PreparedDishAvailableFilter(admin.SimpleListFilter):
    title = 'Доступно'
    parameter_name = 'is_available'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да (есть в наличии)'),
            ('no', 'Нет (нет в наличии)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(quantity__gt=0)
        if self.value() == 'no':
            return queryset.filter(quantity__lte=0)

# Кастомный фильтр для необходимости приготовления
class NeedsPreparationFilter(admin.SimpleListFilter):
    title = 'Нужно приготовить'
    parameter_name = 'needs_preparation'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Да (мало осталось)'),
            ('no', 'Нет (достаточно)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(quantity__lt=F('max_quantity') / 2)
        if self.value() == 'no':
            return queryset.filter(quantity__gte=F('max_quantity') / 2)

#  ГОТОВЫЕ БЛЮДА 
@admin.register(PreparedDish)
class PreparedDishAdmin(admin.ModelAdmin):
    # Управление готовыми блюдами
    list_display = ['dish', 'quantity', 'max_quantity', 'is_available_display', 'needs_preparation_display', 'prepared_at', 'prepared_by']
    list_filter = [PreparedDishAvailableFilter, NeedsPreparationFilter, 'prepared_at']
    search_fields = ['dish__name']
    list_editable = ['quantity', 'max_quantity']
    
    def is_available_display(self, obj):
        return obj.is_available
    is_available_display.short_description = 'Доступно'
    is_available_display.boolean = True
    
    def needs_preparation_display(self, obj):
        return obj.needs_preparation
    needs_preparation_display.short_description = 'Нужно приготовить'
    needs_preparation_display.boolean = True

#  ЭЛЕМЕНТЫ КОМБО-НАБОРА 
class ComboItemInline(admin.TabularInline):
    # Блюда в комбо-наборе
    model = ComboItem
    extra = 1  # Показать 1 пустое поле для добавления

#  КОМБО-НАБОРЫ 
@admin.register(ComboSet)
class ComboSetAdmin(admin.ModelAdmin):
    # Управление комбо-наборами
    list_display = ['name', 'created_by', 'total_price', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']  # Фильтры по активности и дате
    search_fields = ['name', 'created_by__username']  # Поиск по названию и создателю
    inlines = [ComboItemInline]  # Показать блюда в наборе

#  ЗАКАЗЫ КОМБО-НАБОРОВ 
@admin.register(ComboOrder)
class ComboOrderAdmin(admin.ModelAdmin):
    # Управление заказами комбо-наборов
    list_display = ['id', 'combo_set', 'customer', 'status', 'created_at']
    list_filter = ['status', 'created_at']  # Фильтры по статусу и дате
    search_fields = ['customer__username', 'combo_set__name']  # Поиск по ученику и названию набора
    readonly_fields = ['created_at', 'updated_at']  # Нельзя менять даты

#  ПЛАТЕЖИ 
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # Управление платежами
    list_display = ['id', 'user', 'order', 'amount', 'status',
                    'payment_method', 'description', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']  # Фильтры по статусу, способу и дате
    search_fields = ['user__username', 'description', 'order__id']  # Поиск по пользователю, описанию, номеру заказа
    readonly_fields = ['created_at', 'completed_at']  # Дата создания и завершения только для чтения
    list_select_related = ['user', 'order']  # Оптимизация запросов
