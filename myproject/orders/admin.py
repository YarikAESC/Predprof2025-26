from django.contrib import admin
from .models import Category, Dish, Order, OrderItem, Ingredient, DishIngredient, ComboSet, ComboItem, ComboOrder, Payment

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