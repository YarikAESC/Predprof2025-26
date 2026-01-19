from django.contrib import admin

from .models import Category, Dish, Order, OrderItem

# Админка категорий
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']  # Поля в списке
    search_fields = ['name']  # Поиск по имени

# Админка блюд
@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available']  # Поля в списке
    list_filter = ['category', 'is_available']  # Фильтры справа
    search_fields = ['name', 'description']  # Поиск
    list_editable = ['price', 'is_available']  # Редактируемые поля в списке
    
    # Сохранение модели
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Если новый объект
            obj.created_by = request.user  # Записываем создателя
        super().save_model(request, obj, form, change)

# Вложенная админка для элементов заказа
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # Не показывать пустые поля

# Админка заказов
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'total_price', 'created_at']  # Поля в списке
    list_filter = ['status', 'created_at']  # Фильтры
    search_fields = ['customer__username', 'customer__email']  # Поиск по ученику
    inlines = [OrderItemInline]  # Добавляем элементы заказа
    readonly_fields = ['created_at', 'updated_at']  # Только чтение
