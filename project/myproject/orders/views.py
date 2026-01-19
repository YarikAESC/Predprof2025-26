from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from .models import Dish, Order, OrderItem, Category, OrderPickup, Payment, Transaction
from users.models import CustomUser
from .utils import user_can_use_cart, user_can_order

# Главная страница сайта
def home(request):
    return render(request, 'orders/home.html')

# Класс для отображения меню
class MenuView(ListView):
    model = Dish
    template_name = 'orders/menu.html'
    context_object_name = 'dishes'
    
    def dispatch(self, request, *args, **kwargs):
        # Только ученики могут смотреть меню
        if not request.user.is_authenticated or not request.user.is_student():
            messages.error(request, 'Меню доступно только ученикам')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Получение доступных блюд с фильтрацией по категории
        queryset = Dish.objects.filter(is_available=True).select_related('category')
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset
    
    def get_context_data(self, **kwargs):
        # Добавление категорий и количества товаров в корзине в контекст
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        if hasattr(self.request.user, 'is_student') and self.request.user.is_student():
            cart = self.request.session.get('cart', {})
            context['cart_count'] = len(cart)
            context['show_cart'] = True
        else:
            context['cart_count'] = 0
            context['show_cart'] = False
        return context

# Добавление блюда в корзину
@login_required
@user_can_use_cart
def add_to_cart(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if dish_id_str in cart:
        cart[dish_id_str] += 1  # Увеличиваем количество
    else:
        cart[dish_id_str] = 1   # Добавляем новое блюдо
    
    request.session['cart'] = cart
    messages.success(request, f'"{dish.name}" добавлено в корзину')
    return redirect('menu')

# Просмотр корзины
@login_required
@user_can_use_cart
def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    # Формирование списка товаров в корзине
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
            continue  # Пропускаем несуществующие блюда
    
    return render(request, 'orders/cart.html', {
        'cart_items': cart_items,
        'total': total
    })

# Обновление количества товара в корзине
@login_required
@user_can_use_cart
def update_cart(request, dish_id):
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        if quantity and quantity.isdigit():
            quantity = int(quantity)
            if quantity > 0:
                cart[dish_id_str] = quantity  # Обновляем количество
            else:
                cart.pop(dish_id_str, None)   # Удаляем если количество 0
        else:
            cart.pop(dish_id_str, None)       # Удаляем при неверных данных
    
    request.session['cart'] = cart
    return redirect('view_cart')

# Удаление товара из корзины
@login_required
@user_can_use_cart
def remove_from_cart(request, dish_id):
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if dish_id_str in cart:
        del cart[dish_id_str]
        request.session['cart'] = cart
        messages.success(request, 'Блюдо удалено из корзины')
    
    return redirect('view_cart')

# Создание заказа с оплатой с баланса
@login_required
def create_order(request):
    # Только ученики могут оформлять заказы
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут оформлять заказы')
        return redirect('menu')
    
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu')
    
    try:
        # Рассчитываем сумму
        total = 0
        for dish_id_str, quantity in cart.items():
            dish = Dish.objects.get(id=int(dish_id_str), is_available=True)
            total += dish.price * quantity
        
        # Проверяем баланс
        if not request.user.can_afford(total):
            messages.error(request, f'Недостаточно средств. Нужно: {total} ₽, на балансе: {request.user.balance} ₽')
            return redirect('my_balance')
        
        # Создаем заказ
        order = Order.objects.create(
            customer=request.user,
            status='preparing',
            total_price=total
        )
        
        # Добавляем блюда
        for dish_id_str, quantity in cart.items():
            dish = Dish.objects.get(id=int(dish_id_str), is_available=True)
            OrderItem.objects.create(
                order=order,
                dish=dish,
                quantity=quantity,
                price_at_time=dish.price
            )
        
        # Списание с баланса
        if request.user.deduct_balance(total, description=f"Оплата заказа #{order.id}"):
            # Создаем платеж
            Payment.objects.create(
                order=order,
                user=request.user,
                amount=total,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now()
            )
        
        # Очищаем корзину
        request.session['cart'] = {}
        
        messages.success(request, f'Заказ #{order.id} оформлен и оплачен!')
        return redirect('order_detail', order_id=order.id)
        
    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('view_cart')

# Просмотр своих заказов
@login_required
def my_orders(request):
    try:
        # Показываем заказы только ученикам
        if not request.user.is_student():
            messages.error(request, 'Доступно только для учеников')
            return redirect('menu')

        # Показываем только видимые заказы пользователя
        orders = Order.objects.filter(
            customer=request.user,
            is_visible_to_customer=True
        ).order_by('-created_at')

        return render(request, 'orders/my_orders.html', {'orders': orders})
    except Exception as e:
        messages.error(request, f'Ошибка загрузки заказов: {str(e)}')
        return redirect('menu')

# Детальная информация о заказе
@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Проверка прав доступа: админ или владелец заказа
    if not hasattr(request.user, 'role') or (request.user.role != 'admin' and order.customer != request.user):
        messages.error(request, 'У вас нет прав для просмотра этого заказа')
        return redirect('my_orders')
    
    return render(request, 'orders/order_detail.html', {'order': order})

# Отмена заказа
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # Можно отменять только заказы в статусах pending или preparing
    if order.status in ['pending', 'preparing']:
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Заказ #{order.id} отменен')
    else:
        messages.error(request, 'Невозможно отменить заказ в текущем статусе')
    
    return redirect('my_orders')

# Админ-панель
@login_required
def admin_dashboard(request):
    # Только для администраторов
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    # Сбор статистики
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

# Управление блюдами
@login_required
def manage_dishes(request):
    # Только для администраторов
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    dishes = Dish.objects.all().select_related('category')
    categories = Category.objects.all()
    
    return render(request, 'orders/manage_dishes.html', {
        'dishes': dishes,
        'categories': categories,
    })

# Добавление нового блюда
@login_required
def add_dish(request):
    # Только для администраторов
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

# Управление пользователями
@login_required
def manage_users(request):
    # Только для администраторов
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")
    
    users = CustomUser.objects.all()
    return render(request, 'orders/manage_users.html', {'users': users})

# Изменение роли пользователя
@login_required
def change_user_role(request, user_id):
    # Только для администраторов
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

# Обновление статуса заказа
@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        # Логика для повара
        if request.user.is_chef():
            if order.status == 'preparing' and new_status == 'ready':
                order.status = new_status
                order.save()
                messages.success(request, f'Заказ #{order.id} отмечен как готовый!')
            else:
                messages.error(request, 'Невозможно изменить статус')
            return redirect('chef_orders')
        
        # Логика для администратора
        elif request.user.is_admin():
            if new_status in dict(Order.STATUS_CHOICES):
                order.status = new_status
                order.save()
                messages.success(request, f'Статус заказа #{order.id} изменен')
            return redirect('admin_dashboard')
    
    return redirect('menu')

# Страница заказов для повара
@login_required
def chef_orders(request):
    # Только для поваров
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    # Получаем заказы со статусом 'preparing'
    orders = Order.objects.filter(status='preparing').select_related('customer').order_by('created_at')
    
    return render(request, 'orders/chef_orders.html', {'orders': orders})

# Управление заказами (админ)
@login_required  
def manage_orders(request):
    # Только для администраторов
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    orders = Order.objects.all().select_related('customer').order_by('-created_at')
    
    # Обновление статуса заказа
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

# Пользователь отмечает что получил заказ
@login_required
def mark_as_picked(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if order.customer != request.user:
        messages.error(request, 'Вы не можете отметить этот заказ')
        return redirect('my_orders')
    
    if order.status != 'ready':
        messages.error(request, 'Заказ еще не готов')
        return redirect('order_detail', order_id=order_id)
    
    # Создаем отметку о получении
    OrderPickup.objects.get_or_create(
        order=order,
        defaults={'picked_up_by': request.user}
    )
    
    messages.success(request, 'Заказ отмечен как полученный!')
    return redirect('my_orders')

# Отметить заказ как оплаченный (админ)
@login_required
def mark_as_paid(request, order_id):
    if not request.user.is_admin():
        messages.error(request, 'Только администратор')
        return redirect('menu')
    
    order = get_object_or_404(Order, id=order_id)
    
    # Создаем запись о платеже
    payment = Payment.objects.create(
        order=order,
        user=order.customer,
        amount=order.total_price,
        status='paid',
        completed_at=timezone.now()
    )
    
    messages.success(request, f'Заказ #{order.id} отмечен как оплаченный')
    return redirect('statistics')

# Скрытие заказа (отметка как полученного)
@login_required
def hide_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # Можно скрыть только готовые заказы
    if order.status != 'ready':
        messages.error(request, 'Заказ еще не готов к выдаче')
        return redirect('my_orders')

    # Меняем статус и скрываем от пользователя
    order.status = 'delivered'
    order.is_visible_to_customer = False
    order.save()

    messages.success(request, f'Вы забрали заказ #{order.id}')
    return redirect('my_orders')

# Статистика для админа
@login_required
def statistics(request):
    if not request.user.is_admin():
        messages.error(request, 'Только для администраторов')
        return redirect('menu')
    
    today = timezone.now().date()
    
    try:
        # 1. ПОЛЬЗОВАТЕЛИ
        total_users = CustomUser.objects.count()
        total_students = CustomUser.objects.filter(role='student').count()
        total_chefs = CustomUser.objects.filter(role='chef').count()
        total_admins = CustomUser.objects.filter(role='admin').count()
        
        # 2. ЗАКАЗЫ
        total_orders = Order.objects.count()
        today_orders = Order.objects.filter(created_at__date=today).count()
        
        # Завершенные заказы (готовы к выдаче)
        completed_orders = Order.objects.filter(status='ready').count()
        
        # 3. ЗАБРАННЫЕ ЗАКАЗЫ - ИСПРАВЛЕНИЕ
        # Вариант А: через OrderPickup
        picked_up_orders = OrderPickup.objects.count()
        
        # Или Вариант Б: через статус 'delivered'
        delivered_orders = Order.objects.filter(status='delivered').count()
        
        # 4. ОПЛАТЫ
        total_payments = Payment.objects.filter(status='paid')
        total_income = total_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # 5. ПОСЕЩАЕМОСТЬ
        today_logged_users = CustomUser.objects.filter(
            last_login__date=today
        ).order_by('-last_login')
        
        context = {
            # Пользователи
            'total_users': total_users,
            'total_students': total_students,
            'total_chefs': total_chefs,
            'total_admins': total_admins,
            'today_logins': today_logged_users.count(),
            
            # Заказы
            'total_orders': total_orders,
            'today_orders': today_orders,
            'completed_orders': completed_orders,
            'picked_up_orders': picked_up_orders,  # или delivered_orders
            'delivered_orders': delivered_orders,  # добавим оба для теста
            
            # Финансы
            'total_income': total_income,
            'total_payments': total_payments.count(),
        }
        
        # Для отладки - покажем в консоли
        print(f"Забранных заказов (OrderPickup): {picked_up_orders}")
        print(f"Забранных заказов (статус delivered): {delivered_orders}")
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки статистики: {str(e)}')
        print(f"Ошибка в статистике: {str(e)}")  # Отладка
        context = {}
    
    return render(request, 'orders/statistics.html', context)

# Личный кабинет с балансом
@login_required
def my_balance(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    
    # Получаем последние заказы
    recent_orders = Order.objects.filter(customer=request.user).order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'transactions': transactions,
        'recent_orders': recent_orders,
    }
    return render(request, 'orders/my_balance.html', context)

# Пополнение баланса
@login_required
def add_balance(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('my_balance')
            
            # Пополняем баланс
            request.user.add_balance(
                amount, 
                description=f"Пополнение через сайт"
            )
            
            messages.success(request, f'Баланс пополнен на {amount} руб.')
            return redirect('my_balance')
            
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректная сумма')
    
    return render(request, 'orders/add_balance.html')

# Оплата заказа с баланса
@login_required
def pay_with_balance(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status != 'pending':
        messages.error(request, 'Невозможно оплатить этот заказ')
        return redirect('order_detail', order_id=order_id)
    
    if request.user.can_afford(order.total_price):
        # Списание с баланса
        if request.user.deduct_balance(
            order.total_price,
            description=f"Оплата заказа #{order.id}"
        ):
            # Создаем запись о платеже
            payment = Payment.objects.create(
                order=order,
                user=request.user,
                amount=order.total_price,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now()
            )
            
            # Меняем статус заказа
            order.status = 'preparing'
            order.save()
            
            messages.success(request, f'Заказ #{order.id} оплачен с баланса')
            return redirect('order_detail', order_id=order_id)
    
    messages.error(request, 'Недостаточно средств на балансе')
    return redirect('order_detail', order_id=order_id)
