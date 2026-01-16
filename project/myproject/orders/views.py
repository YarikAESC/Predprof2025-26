from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from django.core.exceptions import PermissionDenied
from .models import Dish, Order, OrderItem, Category
from users.models import CustomUser
from .utils import user_can_order

class MenuView(ListView):
    model = Dish
    template_name = 'orders/menu.html'
    context_object_name = 'dishes'
    
    def get_queryset(self):
        queryset = Dish.objects.filter(is_available=True).select_related('category')
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        cart = self.request.session.get('cart', {})
        context['cart_count'] = len(cart)
        return context

@login_required
def add_to_cart(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if dish_id_str in cart:
        cart[dish_id_str] += 1
    else:
        cart[dish_id_str] = 1
    
    request.session['cart'] = cart
    messages.success(request, f'"{dish.name}" добавлено в корзину')
    return redirect('menu')

@login_required
def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    for dish_id_str, quantity in cart.items():
        try:
            dish_id = int(dish_id_str)
            dish = Dish.objects.get(id=dish_id, is_available=True)
            item_total = dish.price * quantity
            cart_items.append({
                'dish': dish,
                'quantity': quantity,
                'total': item_total
            })
            total += item_total
        except (Dish.DoesNotExist, ValueError):
            continue
    
    return render(request, 'orders/cart.html', {
        'cart_items': cart_items,
        'total': total
    })

@login_required
def update_cart(request, dish_id):
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        if quantity and quantity.isdigit():
            quantity = int(quantity)
            if quantity > 0:
                cart[dish_id_str] = quantity
            else:
                cart.pop(dish_id_str, None)
        else:
            cart.pop(dish_id_str, None)
    
    request.session['cart'] = cart
    return redirect('view_cart')

@login_required
def remove_from_cart(request, dish_id):
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if dish_id_str in cart:
        del cart[dish_id_str]
        request.session['cart'] = cart
        messages.success(request, 'Блюдо удалено из корзины')
    
    return redirect('view_cart')

@login_required
def create_order(request):
    """Создание заказа из корзины - сразу со статусом 'preparing'"""
    if not hasattr(request.user, 'role') or request.user.role != 'student':
        messages.error(request, 'Только ученики могут оформлять заказы')
        return redirect('menu')
    
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu')
    
    try:
        order = Order.objects.create(
            customer=request.user,
            status='preparing',
            total_price=0
        )
        
        total = 0
        for dish_id_str, quantity in cart.items():
            dish_id = int(dish_id_str)
            dish = Dish.objects.get(id=dish_id, is_available=True)
            
            OrderItem.objects.create(
                order=order,
                dish=dish,
                quantity=quantity,
                price_at_time=dish.price
            )
            total += dish.price * quantity
        
        order.total_price = total
        order.save()
        
        request.session['cart'] = {}
        
        messages.success(request, f'Заказ #{order.id} успешно оформлен! Начато приготовление.')
        return redirect('order_detail', order_id=order.id)
        
    except Dish.DoesNotExist:
        messages.error(request, 'Некоторые блюда больше не доступны')
        return redirect('view_cart')
    except Exception as e:
        messages.error(request, f'Ошибка при оформлении заказа: {str(e)}')
        return redirect('view_cart')

@login_required
def my_orders(request):
    try:

        orders = Order.objects.filter(
            customer=request.user,
            is_visible_to_customer=True  # ← показываем только видимые
        ).order_by('-created_at')
        
        return render(request, 'orders/my_orders.html', {'orders': orders})
    except Exception as e:
        messages.error(request, f'Ошибка загрузки заказов: {str(e)}')
        return redirect('menu')

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if not hasattr(request.user, 'role') or (request.user.role != 'admin' and order.customer != request.user):
        messages.error(request, 'У вас нет прав для просмотра этого заказа')
        return redirect('my_orders')
    
    return render(request, 'orders/order_detail.html', {'order': order})

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status in ['pending', 'preparing']:
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Заказ #{order.id} отменен')
    else:
        messages.error(request, 'Невозможно отменить заказ в текущем статусе')
    
    return redirect('my_orders')

@login_required
def admin_dashboard(request):
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    total_customers = CustomUser.objects.filter(role='customer').count()
    total_chefs = CustomUser.objects.filter(role='chef').count()
    total_dishes = Dish.objects.count()
    total_orders = Order.objects.count()
    active_orders = Order.objects.exclude(status__in=['delivered', 'cancelled']).count()
    
    context = {
        'total_customers': total_customers,
        'total_chefs': total_chefs,
        'total_dishes': total_dishes,
        'total_orders': total_orders,
        'active_orders': active_orders,
    }
    return render(request, 'orders/admin_dashboard.html', context)

@login_required
def manage_dishes(request):
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    dishes = Dish.objects.all().select_related('category')
    categories = Category.objects.all()
    
    return render(request, 'orders/manage_dishes.html', {
        'dishes': dishes,
        'categories': categories,
    })

@login_required
def add_dish(request):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        category_id = request.POST.get('category')
        
        try:
            category = Category.objects.get(id=category_id)
            dish = Dish.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                created_by=request.user
            )
            messages.success(request, f'Блюдо "{dish.name}" добавлено')
            return redirect('manage_dishes')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
    
    categories = Category.objects.all()
    return render(request, 'orders/add_dish.html', {'categories': categories})

@login_required
def manage_users(request):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")
    
    users = CustomUser.objects.all()
    return render(request, 'orders/manage_users.html', {'users': users})

@login_required
def change_user_role(request, user_id):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ['admin', 'customer', 'chef']:
            user.role = new_role
            user.save()
            messages.success(request, f'Роль пользователя {user.username} изменена на {user.get_role_display()}')
    
    return redirect('manage_users')

@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if request.user.is_chef():
            if order.status == 'preparing' and new_status == 'ready':
                order.status = new_status
                order.save()
                messages.success(request, f'Заказ #{order.id} отмечен как готовый!')
            else:
                messages.error(request, 'Невозможно изменить статус')
            return redirect('chef_orders')
        
        elif request.user.is_admin():
            if new_status in dict(Order.STATUS_CHOICES):
                order.status = new_status
                order.save()
                messages.success(request, f'Статус заказа #{order.id} изменен')
            return redirect('admin_dashboard')
    
    return redirect('menu')

@login_required
def chef_orders(request):
    """Страница заказов для повара"""
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    orders = Order.objects.filter(status='preparing').select_related('customer').order_by('created_at')
    
    # Для отладки
    print(f"Найдено заказов для повара: {orders.count()}")
    for order in orders:
        print(f"Заказ #{order.id}, статус: {order.status}, пользователь: {order.customer.username}")
    
    return render(request, 'orders/chef_orders.html', {'orders': orders})

@login_required  
def manage_orders(request):
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    orders = Order.objects.all().select_related('customer').order_by('-created_at')
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('status')
        
        if order_id and new_status:
            try:
                order = Order.objects.get(id=order_id)
                order.status = new_status
                order.save()
                messages.success(request, f'Статус заказа #{order_id} изменен')
            except Order.DoesNotExist:
                messages.error(request, 'Заказ не найден')
    
    context = {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES if hasattr(Order, 'STATUS_CHOICES') else [],
    }
    return render(request, 'orders/manage_orders.html', context)
@login_required
def hide_order(request, order_id):
    """Скрыть заказ из списка ученика"""
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    order.is_visible_to_customer = False
    order.save()
    messages.success(request, f'Вы забрали заказ #{order.id}')
    return redirect('my_orders')


