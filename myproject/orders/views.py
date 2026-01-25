from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from .models import Dish, Order, OrderItem, Category, OrderPickup, Payment, Transaction, Review, Ingredient, DishIngredient, ComboSet, ComboItem, ComboOrder
from users.models import CustomUser
from .utils import user_can_use_cart
from django.db import models

# Показывает главную страницу сайта
def home(request):
    return render(request, 'orders/home.html')

# Класс для отображения списка блюд
class MenuView(ListView):
    model = Dish
    template_name = 'orders/menu.html'
    context_object_name = 'dishes'

    # Получаем список блюд с фильтрацией
    def get_queryset(self):
        qs = Dish.objects.filter(is_available=True) \
            .select_related('category') \
            .prefetch_related('ingredients__ingredient')

        # Фильтр по категории, если выбран
        category_id = self.request.GET.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Убираем блюда с аллергенами для учеников
        if self.request.user.is_authenticated and self.request.user.is_student():
            user_allergens = self.request.user.allergens.all()
            if user_allergens.exists():
                qs = qs.exclude(
                    ingredients__ingredient__in=user_allergens
                ).distinct()

        return qs

    # Проверяем доступ к меню
    def dispatch(self, request, *args, **kwargs):
        # Только ученики могут смотреть меню
        if not request.user.is_authenticated or not request.user.is_student():
            messages.error(request, 'Меню доступно только ученикам')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    # Добавляем дополнительные данные в шаблон
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()

        # Информация о скрытых блюдах из-за аллергенов
        if self.request.user.is_authenticated and self.request.user.is_student():
            user_allergens = self.request.user.allergens.all()
            if user_allergens.exists():
                all_dishes = Dish.objects.filter(is_available=True)
                hidden_dishes = all_dishes.filter(
                    ingredients__ingredient__in=user_allergens
                ).distinct().count()
                context['hidden_dishes_count'] = hidden_dishes
                context['user_allergens'] = user_allergens

        # Количество товаров в корзине
        if hasattr(self.request.user, 'is_student') and self.request.user.is_student():
            cart = self.request.session.get('cart', {})
            context['cart_count'] = len(cart)
            context['show_cart'] = True
        else:
            context['cart_count'] = 0
            context['show_cart'] = False
        return context

# Добавляет блюдо в корзину пользователя
@login_required
@user_can_use_cart
def add_to_cart(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    # Увеличиваем количество или добавляем новое блюдо
    if dish_id_str in cart:
        cart[dish_id_str] += 1
    else:
        cart[dish_id_str] = 1
    
    request.session['cart'] = cart
    messages.success(request, f'"{dish.name}" добавлено в корзину')
    return redirect('menu')

# Показывает содержимое корзины
@login_required
@user_can_use_cart
def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    # Собираем информацию о каждом блюде в корзине
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

# Меняет количество блюда в корзине
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
                cart.pop(dish_id_str, None)  # Удаляем если 0
        else:
            cart.pop(dish_id_str, None)  # Удаляем если не число
    
    request.session['cart'] = cart
    return redirect('view_cart')

# Удаляет блюдо из корзины
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

# Создает новый заказ и списывает деньги с баланса
@login_required
def create_order(request):
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут оформлять заказы')
        return redirect('menu')

    cart = request.session.get('cart', {})

    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu')

    try:
        # Считаем общую сумму заказа
        total = 0
        for dish_id_str, quantity in cart.items():
            dish = Dish.objects.get(id=int(dish_id_str), is_available=True)
            total += dish.price * quantity

        # Проверяем хватает ли денег на балансе
        if not request.user.can_afford(total):
            messages.error(request, f'Недостаточно средств. Нужно: {total} ₽, на балансе: {request.user.balance} ₽')
            return redirect('my_balance')

        # Создаем заказ в базе данных
        order = Order.objects.create(
            customer=request.user,
            status='preparing',
            total_price=total
        )

        # Добавляем все блюда из корзины в заказ
        for dish_id_str, quantity in cart.items():
            dish = Dish.objects.get(id=int(dish_id_str), is_available=True)
            OrderItem.objects.create(
                order=order,
                dish=dish,
                quantity=quantity,
                price_at_time=dish.price
            )

        # Списываем деньги с баланса
        if request.user.deduct_balance(total, description=f"Оплата заказа #{order.id}"):
            Payment.objects.create(
                order=order,
                user=request.user,
                amount=total,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now(),
                description=f"Оплата заказа #{order.id}"
            )

        # Очищаем корзину после оформления заказа
        request.session['cart'] = {}

        messages.success(request, f'Заказ #{order.id} оформлен и оплачен!')
        return redirect('my_orders')

    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('view_cart')

# Показывает активные заказы пользователя
@login_required
def my_orders(request):
    try:
        if not request.user.is_student():
            messages.error(request, 'Доступно только для учеников')
            return redirect('menu')

        # Заказы в процессе (не завершенные)
        orders = Order.objects.filter(
            customer=request.user,
            status__in=['pending', 'confirmed', 'preparing', 'ready']
        ).order_by('-created_at')

        return render(request, 'orders/my_orders.html', {'orders': orders})
    except Exception as e:
        messages.error(request, f'Ошибка загрузки заказов: {str(e)}')
        return redirect('menu')

# Показывает историю завершенных заказов
@login_required
def order_history(request):
    try:
        if not hasattr(request.user, 'role') or request.user.role != 'student':
            messages.error(request, 'История заказов доступна только ученикам')
            return redirect('home')

        # Завершенные заказы (полученные или забранные)
        orders = Order.objects.filter(
            customer=request.user,
            status__in=['picked_up', 'delivered']
        ).select_related('customer').prefetch_related('items__dish').order_by('-created_at')

        return render(request, 'orders/order_history.html', {
            'orders': orders,
            'user': request.user
        })

    except Exception as e:
        messages.error(request, f'Ошибка загрузки истории заказов: {str(e)}')
        return redirect('my_orders')

# Отмечает что пользователь забрал свой заказ
@login_required
def mark_as_picked(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Проверяем что это заказ текущего пользователя
    if order.customer != request.user:
        messages.error(request, 'Вы не можете отметить этот заказ')
        return redirect('my_orders')
    
    # Проверяем что заказ готов к выдаче
    if order.status != 'ready':
        messages.error(request, 'Заказ еще не готов')
        return redirect('my_orders')
    
    # Меняем статус на "получен"
    order.status = 'picked_up'
    order.save()
    
    # Создаем запись о получении
    OrderPickup.objects.get_or_create(
        order=order,
        defaults={'picked_up_by': request.user}
    )

    messages.success(request, 'Вы забрали заказ! Теперь он в истории заказов.')
    return redirect('order_history')

# Позволяет оставить отзыв на блюдо из заказа
@login_required
def add_review(request, order_id, dish_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # Отзыв можно оставить только на завершенный заказ
    if order.status not in ['delivered', 'picked_up']:
        messages.error(request, 'Отзыв можно оставить только на завершенный заказ')
        return redirect('order_history')
    
    dish = get_object_or_404(Dish, id=dish_id)
    
    # Проверяем что это блюдо действительно было в заказе
    if not order.items.filter(dish=dish).exists():
        messages.error(request, 'Это блюдо не было в заказе')
        return redirect('order_history')
    
    if request.method == 'POST':
        # Сохраняем отзыв из формы
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        Review.objects.create(
            user=request.user,
            dish=dish,
            order=order,
            rating=rating,
            comment=comment
        )
        
        messages.success(request, 'Спасибо за отзыв!')
        return redirect('order_history')
    
    # Показываем форму для отзыва
    return render(request, 'orders/add_review.html', {
        'order': order,
        'dish': dish
    })

# Показывает подробную информацию о заказе
@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order = Order.objects.prefetch_related(
        'items__dish__ingredients__ingredient',
        'customer__allergens').get(id=order_id)
    
    # Проверяем права: админ или владелец заказа
    if not hasattr(request.user, 'role') or (request.user.role != 'admin' and order.customer != request.user):
        messages.error(request, 'У вас нет прав для просмотра этого заказа')
        return redirect('my_orders')
    
    return render(request, 'orders/order_detail.html', {'order': order})

# Отменяет заказ пользователя
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # Можно отменять только заказы в определенных статусах
    if order.status in ['pending', 'preparing']:
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Заказ #{order.id} отменен')
    else:
        messages.error(request, 'Невозможно отменить заказ в текущем статусе')
    
    return redirect('my_orders')

# Панель администратора с общей статистикой
@login_required
def admin_dashboard(request):
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    # Собираем статистические данные
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

# Управление блюдами (админ)
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

# Добавление нового блюда (админ)
@login_required
def add_dish(request):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")

    if request.method == 'POST':
        # Получаем данные из формы
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        category_id = request.POST.get('category')
        is_available = bool(request.POST.get('is_available'))
        image = request.FILES.get('image')

        try:
            category = Category.objects.get(id=category_id)
            # Создаем блюдо в базе данных
            dish = Dish.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                is_available=is_available,
                image=image,
                created_by=request.user
            )

            # Добавляем ингредиенты блюда
            ingredients = request.POST.getlist('ingredient')
            quantities = request.POST.getlist('quantity')
            for ing_id, qty in zip(ingredients, quantities):
                if ing_id and qty:
                    DishIngredient.objects.create(
                        dish=dish,
                        ingredient_id=ing_id,
                        quantity=qty
                    )

            messages.success(request, f'Блюдо "{dish.name}" и ингредиенты добавлены!')
            return redirect('manage_dishes')

        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')

    # Показываем форму для добавления блюда
    categories = Category.objects.all()
    ingredients = Ingredient.objects.all()
    return render(request, 'orders/add_dish.html', {
        'categories': categories,
        'ingredients': ingredients
    })

# Редактирование существующего блюда (админ)
@login_required
def edit_dish(request, dish_id):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")

    dish = get_object_or_404(Dish, id=dish_id)

    if request.method == 'POST':
        # Обновляем данные блюда
        dish.name = request.POST.get('name')
        dish.description = request.POST.get('description')
        dish.price = request.POST.get('price')
        dish.category_id = request.POST.get('category')
        dish.is_available = bool(request.POST.get('is_available'))
        if request.FILES.get('image'):
            dish.image = request.FILES.get('image')
        dish.save()

        # Обновляем ингредиенты (удаляем старые, добавляем новые)
        DishIngredient.objects.filter(dish=dish).delete()
        ingredients = request.POST.getlist('ingredient')
        quantities = request.POST.getlist('quantity')
        for ing_id, qty in zip(ingredients, quantities):
            if ing_id and qty:
                DishIngredient.objects.create(
                    dish=dish,
                    ingredient_id=ing_id,
                    quantity=qty
                )

        messages.success(request, f'Блюдо "{dish.name}" и ингредиенты обновлены!')
        return redirect('manage_dishes')

    # Показываем форму редактирования с текущими данными
    categories = Category.objects.all()
    ingredients = Ingredient.objects.all()
    existing_ingredients = dish.ingredients.all()
    return render(request, 'orders/edit_dish.html', {
        'dish': dish,
        'categories': categories,
        'ingredients': ingredients,
        'existing_ingredients': existing_ingredients
    })

# Изменение роли пользователя (админ)
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

# Изменение статуса заказа
@login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        # Если это повар
        if request.user.is_chef():
            if order.status == 'preparing' and new_status == 'ready':
                order.status = new_status
                order.save()
                messages.success(request, f'Заказ #{order.id} отмечен как готовый!')
            else:
                messages.error(request, 'Невозможно изменить статус')
            return redirect('chef_orders')
        
        # Если это админ
        elif request.user.is_admin():
            if new_status in dict(Order.STATUS_CHOICES):
                order.status = new_status
                order.save()
                messages.success(request, f'Статус заказа #{order.id} изменен')
            return redirect('admin_dashboard')
    
    return redirect('menu')

# Заказы для повара (которые нужно приготовить)
@login_required
def chef_orders(request):
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    orders = Order.objects.filter(status='preparing') \
        .select_related('customer') \
        .prefetch_related(
        'items__dish__ingredients__ingredient',
        'customer__allergens') \
        .order_by('created_at')
    
    return render(request, 'orders/chef_orders.html', {'orders': orders})

# Управление всеми заказами (админ)
@login_required  
def manage_orders(request):
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')

    orders = Order.objects.all() \
        .select_related('customer') \
        .prefetch_related(
        'items__dish__ingredients__ingredient',
        'customer__allergens') \
        .order_by('-created_at')
    
    # Обработка изменения статуса заказа админом
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

# Отметка заказа как оплаченного (админ)
@login_required
def mark_as_paid(request, order_id):
    if not request.user.is_admin():
        messages.error(request, 'Только администратор')
        return redirect('menu')
    
    order = get_object_or_404(Order, id=order_id)
    
    # Создаем запись об оплате
    Payment.objects.create(
        order=order,
        user=order.customer,
        amount=order.total_price,
        status='paid',
        completed_at=timezone.now()
    )
    
    messages.success(request, f'Заказ #{order.id} отмечен как оплаченный')
    return redirect('statistics')

# Статистика для администратора
@login_required
def statistics(request):
    if not request.user.is_admin():
        messages.error(request, 'Только для администраторов')
        return redirect('menu')
    
    today = timezone.now().date()
    
    try:
        # Статистика по пользователям
        total_users = CustomUser.objects.count()
        total_students = CustomUser.objects.filter(role='student').count()
        total_chefs = CustomUser.objects.filter(role='chef').count()
        total_admins = CustomUser.objects.filter(role='admin').count()

        recent_users = CustomUser.objects.all().order_by('-date_joined')[:10]

        # Статистика по заказам
        total_orders = Order.objects.count()
        today_orders = Order.objects.filter(created_at__date=today).count()
        completed_orders = Order.objects.filter(status='ready').count()
        picked_up_orders = OrderPickup.objects.count()
        delivered_orders = Order.objects.filter(status='delivered').count()
        
        # Финансовая статистика
        total_payments = Payment.objects.filter(status='paid')
        total_income = total_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        today_payments = Payment.objects.filter(
            status='paid',
            created_at__date=today
        )
        today_income = today_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        # Статистика активности
        today_logged_users = CustomUser.objects.filter(
            last_login__date=today
        ).order_by('-last_login')
        
        context = {
            'total_users': total_users,
            'total_students': total_students,
            'total_chefs': total_chefs,
            'total_admins': total_admins,
            'recent_users': recent_users,
            'today_logged_users': today_logged_users,
            'today_logins': today_logged_users.count(),
            
            'total_orders': total_orders,
            'today_orders': today_orders,
            'completed_orders': completed_orders,
            'picked_up_orders': picked_up_orders,
            'delivered_orders': delivered_orders,
            
            'total_income': total_income,
            'today_income': today_income,
            'total_payments': total_payments.count(),
            'today_payments': today_payments.count(),
        }
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки статистики: {str(e)}')
        context = {}
    
    return render(request, 'orders/statistics.html', context)

# Личный кабинет с балансом пользователя
@login_required
def my_balance(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    
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

            # Пополняем баланс пользователя
            request.user.add_balance(
                amount,
                description=f"Пополнение через сайт"
            )

            # Создаем запись о платеже
            Payment.objects.create(
                user=request.user,
                amount=amount,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now(),
                description=f"Пополнение баланса"
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
        # Списываем деньги с баланса
        if request.user.deduct_balance(
                order.total_price,
                description=f"Оплата заказа #{order.id}"
        ):
            # Создаем запись об оплате
            payment = Payment.objects.create(
                order=order,
                user=request.user,
                amount=order.total_price,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now(),
                description=f"Оплата заказа #{order.id}"
            )

            # Меняем статус заказа
            order.status = 'preparing'
            order.save()

            messages.success(request, f'Заказ #{order.id} оплачен с баланса')
            return redirect('order_detail', order_id=order_id)

    messages.error(request, 'Недостаточно средств на балансе')
    return redirect('order_detail', order_id=order_id)

# Добавление нового ингредиента (админ)
@login_required
def add_ingredient(request):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        unit = request.POST.get('unit', '').strip()
        if name and unit:
            # Проверяем нет ли уже такого ингредиента
            obj, created = Ingredient.objects.get_or_create(
                name__iexact=name,
                defaults={'name': name, 'unit': unit}
            )
            if created:
                messages.success(request, f'Ингредиент «{obj.name}» добавлен.')
            else:
                messages.warning(request, 'Такой ингредиент уже есть.')
        else:
            messages.error(request, 'Заполните оба поля.')
        return redirect('manage_dishes')

    return redirect('manage_dishes')

# Управление пользователями (админ)
@login_required
def manage_users(request):
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")

    users = CustomUser.objects.all()
    return render(request, 'orders/manage_users.html', {'users': users})

# Главная страница комбо-наборов
@login_required
def my_combo(request):
    try:
        combo_sets_count = ComboSet.objects.filter(created_by=request.user).count()
    except:
        combo_sets_count = 0
    
    context = {
        'combo_sets_count': combo_sets_count,
        'user': request.user
    }
    return render(request, 'orders/combo.html', context) 

# Создание комбо-набора из корзины
@login_required
@user_can_use_cart
def create_combo_set(request):
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут создавать комбо-наборы')
        return redirect('menu')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        max_orders = request.POST.get('max_orders', '1').strip()

        if not name:
            messages.error(request, 'Введите название набора')
            return redirect('view_cart')

        try:
            max_orders = int(max_orders)
            if max_orders < 1 or max_orders > 100:
                messages.error(request, 'Количество повторов должно быть от 1 до 100')
                return redirect('view_cart')
        except ValueError:
            messages.error(request, 'Некорректное количество повторов')
            return redirect('view_cart')

        # Собираем блюда из формы
        cart_items = []
        single_price = 0

        for key, value in request.POST.items():
            if key.startswith('quantity_') and value:
                try:
                    dish_id = int(key.replace('quantity_', ''))
                    quantity = int(value)
                    if quantity > 0:
                        dish = Dish.objects.get(id=dish_id, is_available=True)
                        item_total = dish.price * quantity
                        cart_items.append({
                            'dish': dish,
                            'quantity': quantity,
                            'total': item_total
                        })
                        single_price += item_total
                except (ValueError, Dish.DoesNotExist):
                    continue

        if not cart_items:
            messages.error(request, 'Добавьте хотя бы одно блюдо в набор')
            return redirect('view_cart')

        try:
            # Общая стоимость = цена одного набора * количество повторов
            total_price = single_price * max_orders

            # Проверяем хватает ли денег
            if not request.user.can_afford(total_price):
                messages.error(request,
                               f'Недостаточно средств. Нужно: {total_price} ₽, на балансе: {request.user.balance} ₽')
                return redirect('my_balance')

            # Создаем комбо-набор в базе данных
            combo_set = ComboSet.objects.create(
                name=name,
                description=description,
                created_by=request.user,
                total_price=single_price,
                is_active=True,
                max_orders=max_orders,
                orders_used=0
            )

            # Добавляем блюда в набор
            for item in cart_items:
                ComboItem.objects.create(
                    combo_set=combo_set,
                    dish=item['dish'],
                    quantity=item['quantity']
                )

            # Списываем деньги с баланса
            if request.user.deduct_balance(total_price,
                                           description=f"Оплата комбо-набора '{name}' (x{max_orders} заказов по {single_price} ₽)"):
                Payment.objects.create(
                    user=request.user,
                    amount=total_price,
                    status='paid',
                    payment_method='balance',
                    completed_at=timezone.now(),
                    description=f"Оплата комбо-набора '{name}' (x{max_orders} заказов по {single_price} ₽)"
                )

            messages.success(request,
                             f'Комбо-набор "{name}" создан! Оплачено {total_price} ₽ за {max_orders} заказов.')
            return redirect('my_combo_sets')

        except Exception as e:
            messages.error(request, f'Ошибка создания набора: {str(e)}')
            return redirect('view_cart')

    # Показываем форму с данными из корзины
    cart = request.session.get('cart', {})
    cart_items = []
    single_price = 0

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
            single_price += item_total
        except (Dish.DoesNotExist, ValueError):
            continue

    if not cart_items:
        messages.warning(request, 'Добавьте блюда в корзину для создания набора')
        return redirect('menu')

    return render(request, 'orders/create_combo_set.html', {
        'cart_items': cart_items,
        'single_price': single_price,
        'total': single_price
    })

# Список комбо-наборов пользователя
@login_required
def my_combo_sets(request):
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут создавать комбо-наборы')
        return redirect('menu')

    combo_sets = ComboSet.objects.filter(
        created_by=request.user
    ).filter(
        models.Q(is_active=True) | models.Q(orders_used__lt=models.F('max_orders'))
    ).prefetch_related('items__dish').order_by('-created_at')

    return render(request, 'orders/my_combo_sets.html', {
        'combo_sets': combo_sets
    })

# Заказ комбо-набора
@login_required
def order_combo_set(request, combo_id):
    combo_set = get_object_or_404(ComboSet, id=combo_id, is_active=True)

    # Проверяем не исчерпан ли лимит заказов
    if combo_set.remaining_orders <= 0:
        messages.error(request, 'Лимит заказов этого набора исчерпан')
        return redirect('my_combo_sets')

    if combo_set.created_by != request.user:
        messages.error(request, 'Вы не можете заказать этот набор')
        return redirect('my_combo_sets')

    # Создаем заказ комбо-набора
    combo_order = ComboOrder.objects.create(
        combo_set=combo_set,
        customer=request.user,
        status='preparing'
    )

    # Создаем обычный заказ для повара
    order = Order.objects.create(
        customer=request.user,
        status='preparing',
        total_price=combo_set.total_price,
        notes=f"Комбо-набор: {combo_set.name}"
    )

    # Добавляем блюда в заказ
    for item in combo_set.items.all():
        OrderItem.objects.create(
            order=order,
            dish=item.dish,
            quantity=item.quantity,
            price_at_time=item.dish.price
        )
    # Увеличиваем счетчик использования набора
    combo_set.increment_usage()
    messages.success(request,f'Заказ комбо-набора "{combo_set.name}" создан! Повар получил уведомление.')
    return redirect('my_combo_orders')

# Заказы комбо-наборов пользователя
@login_required
def my_combo_orders(request):
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут заказывать комбо-наборы')
        return redirect('menu')

    combo_orders = ComboOrder.objects.filter(
        customer=request.user
    ).select_related('combo_set').order_by('-created_at')

    return render(request, 'orders/my_combo_orders.html', {
        'combo_orders': combo_orders
    })

# Отмена заказа комбо-набора
@login_required
def cancel_combo_order(request, order_id):
    combo_order = get_object_or_404(ComboOrder, id=order_id, customer=request.user)

    if combo_order.status in ['preparing']:
        combo_order.status = 'cancelled'
        combo_order.save()
        messages.success(request, f'Заказ комбо-набора отменен')
    else:
        messages.error(request, 'Невозможно отменить заказ в текущем статусе')

    return redirect('my_combo_orders')

# Заказы комбо-наборов для повара
@login_required
def chef_combo_orders(request):
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')

    combo_orders = ComboOrder.objects.filter(
        status='preparing'
    ).select_related('combo_set', 'customer').prefetch_related(
        'combo_set__items__dish'
    ).order_by('created_at')

    return render(request, 'orders/chef_combo_orders.html', {
        'combo_orders': combo_orders
    })

# Изменение статуса заказа комбо-набора (повар)
@login_required
def update_combo_order_status(request, order_id):
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')

    combo_order = get_object_or_404(ComboOrder, id=order_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status in ['ready', 'preparing']:
            combo_order.status = new_status
            combo_order.save()

            if new_status == 'ready':
                messages.success(request, f'Комбо-набор #{combo_order.id} отмечен как готовый!')
            else:
                messages.success(request, f'Статус комбо-набора обновлен')

    return redirect('chef_combo_orders')