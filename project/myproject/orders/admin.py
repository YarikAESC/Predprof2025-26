from django.contrib import admin

from .models import Category, Dish, Order, OrderItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'is_available']
    list_filter = ['category', 'is_available']
    search_fields = ['name', 'description']
    list_editable = ['price', 'is_available']
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Если объект создается впервые
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer__username', 'customer__email']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at', 'updated_at']
