from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, InvalidOperation
from django.db import models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Dish, Order, OrderItem, IngredientCost, Category, OrderPickup, Payment, Transaction, Review, Ingredient, DishIngredient, ComboSet, ComboItem, ComboOrder, IngredientStock, StockHistory, PreparedDish
from users.models import CustomUser
from .utils import user_can_use_cart


#  ОСНОВНЫЕ СТРАНИЦЫ 

def home(request):
    # Показывает главную страницу сайта
    context = {}
    
    if request.user.is_authenticated and request.user.is_student():
        context['available_ingredients'] = Ingredient.objects.all().order_by('name')
    
    return render(request, 'orders/home.html', context)


class MenuView(ListView):
    # Класс для отображения списка блюд
    model = Dish
    template_name = 'orders/menu.html'
    context_object_name = 'dishes'

    def get_queryset(self):
        # Получаем список блюд
        qs = Dish.objects.all().select_related('category').prefetch_related('ingredients__ingredient')
        category_id = self.request.GET.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if self.request.user.is_authenticated and self.request.user.is_student():
            user_allergens = self.request.user.allergens.all()
            if user_allergens.exists():
                qs = qs.exclude(ingredients__ingredient__in=user_allergens).distinct()
        return qs

    def dispatch(self, request, *args, **kwargs):
        # Проверяем доступ к меню
        if not request.user.is_authenticated or not request.user.is_student():
            messages.error(request, 'Меню доступно только ученикам')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Добавляем дополнительные данные в шаблон
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        
        prepared_dishes = {}
        for prepared in PreparedDish.objects.all():
            prepared_dishes[prepared.dish.id] = prepared.quantity
        
        dishes_with_info = []
        for dish in context['dishes']:
            prepared_quantity = prepared_dishes.get(dish.id, 0)
            dish.prepared_quantity = prepared_quantity
            
            
            
            dishes_with_info.append(dish)
        
        context['dishes'] = dishes_with_info

        if self.request.user.is_authenticated and self.request.user.is_student():
            user_allergens = self.request.user.allergens.all()
            if user_allergens.exists():
                all_dishes = Dish.objects.all()
                hidden_dishes = all_dishes.filter(ingredients__ingredient__in=user_allergens).distinct().count()
                context['hidden_dishes_count'] = hidden_dishes
                context['user_allergens'] = user_allergens

        if hasattr(self.request.user, 'is_student') and self.request.user.is_student():
            cart = self.request.session.get('cart', {})
            context['cart_count'] = len(cart)
            context['show_cart'] = True
        else:
            context['cart_count'] = 0
            context['show_cart'] = False
            
        return context


#  УПРАВЛЕНИЕ АЛЛЕРГЕНАМИ 

@login_required
def add_allergen(request):
    # Быстрое добавление аллергена со главной страницы
    if not request.user.is_student():
        messages.error(request, 'Только для учеников')
        return redirect('home')
    
    if request.method == 'POST':
        allergen_id = request.POST.get('allergen_id')
        if allergen_id:
            try:
                allergen = Ingredient.objects.get(id=allergen_id)
                if allergen not in request.user.allergens.all():
                    request.user.allergens.add(allergen)
                    messages.success(request, f'Аллерген "{allergen.name}" добавлен')
                else:
                    messages.warning(request, 'Этот аллерген уже добавлен')
            except Ingredient.DoesNotExist:
                messages.error(request, 'Аллерген не найден')
    
    return redirect('home')


@login_required
def remove_allergen(request, allergen_id):
    # Удаление аллергена со главной страницы
    if not request.user.is_student():
        messages.error(request, 'Только для учеников')
        return redirect('home')
    
    allergen = get_object_or_404(Ingredient, id=allergen_id)
    if allergen in request.user.allergens.all():
        request.user.allergens.remove(allergen)
        messages.success(request, f'Аллерген "{allergen.name}" удален')
    
    return redirect('home')


#  КОРЗИНА 

@login_required
@user_can_use_cart
def add_to_cart(request, dish_id):
    # Добавление блюда в корзину
    dish = get_object_or_404(Dish, id=dish_id)
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    prepared_dish = PreparedDish.objects.filter(dish=dish).first()
    prepared_quantity = prepared_dish.quantity if prepared_dish else 0
        

    
    if dish_id_str in cart:
        cart[dish_id_str] += 1
    else:
        cart[dish_id_str] = 1
    
    request.session['cart'] = cart
    messages.success(request, f'"{dish.name}" добавлено в корзину')
    return redirect('menu')

@login_required
@user_can_use_cart
def view_cart(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    for dish_id_str, quantity in cart.items():
        try:
            dish = Dish.objects.get(id=int(dish_id_str))
            item_total = dish.price * quantity
            
            # Проверка доступного количества ТОЛЬКО из готовых
            prepared_dishes = PreparedDish.objects.filter(dish=dish)
            max_available = sum(pd.quantity for pd in prepared_dishes)
            
            cart_items.append({
                'dish': dish,
                'quantity': quantity,
                'total': item_total,
                'max_available': max_available  # Доступно только из готовых
            })
            total += item_total
        except (Dish.DoesNotExist, ValueError):
            continue
    
    return render(request, 'orders/cart.html', {
        'cart_items': cart_items,
        'total': total
    })


@login_required
@user_can_use_cart
def update_cart(request, dish_id):
    # Меняет количество блюда в корзине с проверкой доступности из готовых
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        if quantity and quantity.isdigit():
            quantity = int(quantity)
            
            # Проверяем доступность блюда ИЗ ГОТОВЫХ
            try:
                dish = Dish.objects.get(id=dish_id)
                # Считаем только готовые блюда
                prepared_dishes = PreparedDish.objects.filter(dish=dish)
                max_available = sum(pd.quantity for pd in prepared_dishes)
                
                # Если количество превышает доступное
                if quantity > max_available:
                    messages.warning(request, 
                        f'Блюдо "{dish.name}" доступно только в количестве {max_available} шт. '
                        f'Вы указали {quantity} шт.'
                    )
                    quantity = max_available  # Автоматически ограничиваем максимумом
                
                if quantity > 0:
                    cart[dish_id_str] = quantity
                else:
                    cart.pop(dish_id_str, None)
                    messages.info(request, f'Блюдо "{dish.name}" удалено из корзины')
                    
            except Dish.DoesNotExist:
                cart.pop(dish_id_str, None)
                messages.error(request, 'Блюдо не найдено')
                
        else:
            cart.pop(dish_id_str, None)
    
    request.session['cart'] = cart
    return redirect('view_cart')

@login_required
@user_can_use_cart
def remove_from_cart(request, dish_id):
    # Удаляет блюдо из корзины
    cart = request.session.get('cart', {})
    dish_id_str = str(dish_id)
    
    if dish_id_str in cart:
        del cart[dish_id_str]
        request.session['cart'] = cart
        messages.success(request, 'Блюдо удалено из корзины')
    
    return redirect('view_cart')


@login_required
def create_order(request):
    # Создание заказа из корзины
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут оформлять заказы')
        return redirect('menu')

    cart = request.session.get('cart', {})

    if not cart:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('menu')

    try:
        unavailable_items = []
        order_items = []
        total = 0
        
        for dish_id_str, quantity in cart.items():
            try:
                dish = Dish.objects.get(id=int(dish_id_str))
                
                # Проверяем максимально доступное количество
                max_available = 0
                
                # 1. Проверяем готовые блюда
                prepared_dishes = PreparedDish.objects.filter(dish=dish)
                prepared_available = sum(pd.quantity for pd in prepared_dishes)
                
                # 2. Проверяем возможность приготовить из ингредиентов
                can_prepare_max = 0
                if dish.check_availability(1)[0]:  # Если можно приготовить хотя бы 1
                    # Находим максимальное количество, которое можно приготовить
                    can_prepare_max = dish.check_availability(100)[1]  # Проверяем на большое число
                    if isinstance(can_prepare_max, list):
                        # Если check_availability возвращает список недостающих ингредиентов
                        # Нужно рассчитать максимальное количество на основе ингредиентов
                        max_from_ingredients = float('inf')
                        for ingredient in dish.ingredients.all():
                            try:
                                stock = ingredient.ingredient.stock
                                if ingredient.quantity > 0:
                                    available_qty = int(stock.current_quantity // ingredient.quantity)
                                    max_from_ingredients = min(max_from_ingredients, available_qty)
                            except IngredientStock.DoesNotExist:
                                max_from_ingredients = 0
                                break
                        can_prepare_max = max_from_ingredients if max_from_ingredients != float('inf') else 0
                
                # Суммируем доступное количество
                max_available = prepared_available + can_prepare_max
                
                # Проверяем, достаточно ли доступного количества
                if max_available >= quantity:
                    # Достаточно, определяем источник
                    is_prepared = (prepared_available >= quantity)
                    prepared_dish_for_reservation = prepared_dishes.first() if prepared_dishes.exists() else None
                    
                    order_items.append({
                        'dish': dish,
                        'quantity': quantity,
                        'is_prepared': is_prepared,
                        'prepared_dish': prepared_dish_for_reservation,
                        'prepared_available': prepared_available,
                        'can_prepare_max': can_prepare_max,
                        'max_available': max_available
                    })
                    total += dish.price * quantity
                else:
                    # Недостаточно доступного количества
                    available_sources = []
                    if prepared_available > 0:
                        available_sources.append(f"готовых: {prepared_available}")
                    if can_prepare_max > 0:
                        available_sources.append(f"можно приготовить: {can_prepare_max}")
                    
                    unavailable_items.append({
                        'dish': dish,
                        'quantity': quantity,
                        'max_available': max_available,
                        'available_sources': ", ".join(available_sources) if available_sources else "нет",
                        'reason': 'not_enough_quantity'
                    })
                    
            except Dish.DoesNotExist:
                unavailable_items.append({
                    'dish_id': dish_id_str,
                    'quantity': quantity,
                    'reason': 'not_found'
                })
        
        if unavailable_items:
            messages.error(request, 'Некоторые блюда недоступны в запрошенном количестве')
            return render(request, 'orders/order_unavailable.html', {
                'unavailable_items': unavailable_items,
                'cart': cart
            })
        
        if not request.user.can_afford(total):
            messages.error(request, f'Недостаточно средств. Нужно: {total} ₽, на балансе: {request.user.balance} ₽')
            return redirect('my_balance')

        order = Order.objects.create(customer=request.user, status='pending', total_price=total)

        # Процесс резервирования и создания элементов заказа
        for item in order_items:
            if item['is_prepared']:
                # Используем готовые блюда
                prepared_dish = item['prepared_dish']
                if prepared_dish:
                    # Резервируем из готовых
                    prepared_dish.quantity -= item['quantity']
                    prepared_dish.save()
                
                OrderItem.objects.create(
                    order=order,
                    dish=item['dish'],
                    quantity=item['quantity'],
                    price_at_time=item['dish'].price,
                    status='ready'
                )
            else:
                # Нужно приготовить (частично или полностью из ингредиентов)
                success, _ = item['dish'].reserve_ingredients(item['quantity'], request.user)
                if success:
                    OrderItem.objects.create(
                        order=order,
                        dish=item['dish'],
                        quantity=item['quantity'],
                        price_at_time=item['dish'].price,
                        status='preparing'
                    )
                else:
                    order.delete()
                    messages.error(request, 'Произошла ошибка при резервировании ингредиентов')
                    return redirect('view_cart')
        
        # Определяем статус заказа
        all_items = order.items.all()
        if all_items.count() > 0:
            all_ready = all(item.status == 'ready' for item in all_items)
            if all_ready:
                order.status = 'ready'
            else:
                order.status = 'preparing'
            order.save()
        
        # Оплата
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

        # Очищаем корзину
        request.session['cart'] = {}
        
        messages.success(request, f'Заказ #{order.id} оформлен!')
        return redirect('my_orders')

    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('view_cart')


@login_required
def my_orders(request):
    # Показывает активные заказы пользователя
    try:
        if not request.user.is_student():
            messages.error(request, 'Доступно только для ученикам')
            return redirect('menu')

        orders = Order.objects.filter(customer=request.user, status__in=['pending', 'confirmed', 'preparing', 'ready']).order_by('-created_at')

        return render(request, 'orders/my_orders.html', {'orders': orders})
    except Exception as e:
        messages.error(request, f'Ошибка загрузки заказов: {str(e)}')
        return redirect('menu')


@login_required
def order_history(request):
    # Показывает историю завершенных заказов
    try:
        if not hasattr(request.user, 'role') or request.user.role != 'student':
            messages.error(request, 'История заказов доступна только ученикам')
            return redirect('home')

        orders = Order.objects.filter(customer=request.user, status__in=['picked_up', 'delivered']).select_related('customer').prefetch_related('items__dish').order_by('-created_at')

        return render(request, 'orders/order_history.html', {'orders': orders, 'user': request.user})

    except Exception as e:
        messages.error(request, f'Ошибка загрузки истории заказов: {str(e)}')
        return redirect('my_orders')


@login_required
def mark_as_picked(request, order_id):
    # Отмечает что пользователь забрал свой заказ
    order = get_object_or_404(Order, id=order_id)
    
    if order.customer != request.user:
        messages.error(request, 'Вы не можете отметить этот заказ')
        return redirect('my_orders')
    
    if order.status != 'ready':
        messages.error(request, 'Заказ еще не готов')
        return redirect('my_orders')
    
    order.status = 'picked_up'
    order.save()
    
    OrderPickup.objects.get_or_create(order=order, defaults={'picked_up_by': request.user})

    messages.success(request, 'Вы забрали заказ! Теперь он в истории заказов.')
    return redirect('order_history')


@login_required
def add_review(request, order_id, dish_id):
    # Позволяет оставить отзыв на блюдо из заказа
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status not in ['delivered', 'picked_up']:
        messages.error(request, 'Отзыв можно оставить только на завершенный заказ')
        return redirect('order_history')
    
    dish = get_object_or_404(Dish, id=dish_id)
    
    if not order.items.filter(dish=dish).exists():
        messages.error(request, 'Это блюдо не было в заказе')
        return redirect('order_history')
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        Review.objects.create(user=request.user, dish=dish, order=order, rating=rating, comment=comment)
        
        messages.success(request, 'Спасибо за отзыв!')
        return redirect('order_history')
    
    return render(request, 'orders/add_review.html', {'order': order, 'dish': dish})


@login_required
def order_detail(request, order_id):
    # Показывает подробную информацию о заказе
    order = get_object_or_404(Order, id=order_id)
    order = Order.objects.prefetch_related('items__dish__ingredients__ingredient', 'customer__allergens').get(id=order_id)
    
    if not hasattr(request.user, 'role') or (request.user.role != 'admin' and order.customer != request.user):
        messages.error(request, 'У вас нет прав для просмотра этого заказа')
        return redirect('my_orders')
    
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def cancel_order(request, order_id):
    # Отменяет заказ пользователя
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status in ['pending', 'preparing']:
        order.status = 'cancelled'
        order.save()
        messages.success(request, f'Заказ #{order.id} отменен')
    else:
        messages.error(request, 'Невозможно отменить заказ в текущем статусе')
    
    return redirect('my_orders')


#  БАЛАНС И ОПЛАТА 

@login_required
def my_balance(request):
    # Личный кабинет с балансом пользователя
    transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
    recent_orders = Order.objects.filter(customer=request.user).order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'transactions': transactions,
        'recent_orders': recent_orders,
    }
    return render(request, 'orders/my_balance.html', context)


@login_required
def add_balance(request):
    # Пополнение баланса
    if request.method == 'POST':
        amount = request.POST.get('amount')

        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('my_balance')

            request.user.add_balance(amount, description=f"Пополнение через сайт")

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


@login_required
def pay_with_balance(request, order_id):
    # Оплата заказа с баланса
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    if order.status != 'pending':
        messages.error(request, 'Невозможно оплатить этот заказ')
        return redirect('order_detail', order_id=order_id)

    if request.user.can_afford(order.total_price):
        if request.user.deduct_balance(order.total_price, description=f"Оплата заказа #{order.id}"):
            Payment.objects.create(
                order=order,
                user=request.user,
                amount=order.total_price,
                status='paid',
                payment_method='balance',
                completed_at=timezone.now(),
                description=f"Оплата заказа #{order.id}"
            )

            order.status = 'preparing'
            order.save()

            messages.success(request, f'Заказ #{order.id} оплачен с баланса')
            return redirect('order_detail', order_id=order_id)

    messages.error(request, 'Недостаточно средств на балансе')
    return redirect('order_detail', order_id=order_id)


#  КОМБО-НАБОРЫ 

# КОМБО-НАБОРЫ (с предоплатой за несколько готовых заказов)

@login_required
def my_combo(request):
    try:
        combo_sets_count = ComboSet.objects.filter(created_by=request.user).count()
    except:
        combo_sets_count = 0
    
    context = {'combo_sets_count': combo_sets_count, 'user': request.user}
    return render(request, 'orders/combo.html', context)


@login_required
@user_can_use_cart
def create_combo_set(request):
    # Создание комбо-набора с предоплатой за несколько заказов
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
                messages.error(request, 'Количество заказов должно быть от 1 до 100')
                return redirect('view_cart')
        except ValueError:
            messages.error(request, 'Некорректное количество заказов')
            return redirect('view_cart')

        cart_items = []
        single_price = 0

        for key, value in request.POST.items():
            if key.startswith('quantity_') and value:
                try:
                    dish_id = int(key.replace('quantity_', ''))
                    quantity = int(value)
                    if quantity > 0:
                        dish = Dish.objects.get(id=dish_id)
                        item_total = dish.price * quantity
                        cart_items.append({'dish': dish, 'quantity': quantity, 'total': item_total})
                        single_price += item_total
                except (ValueError, Dish.DoesNotExist):
                    continue

        if not cart_items:
            messages.error(request, 'Добавьте хотя бы одно блюдо в набор')
            return redirect('view_cart')

        try:
            # Рассчитываем общую стоимость предоплаты
            total_price = single_price * max_orders

            # Проверяем баланс
            if not request.user.can_afford(total_price):
                messages.error(request, f'Недостаточно средств. Нужно: {total_price} ₽, на балансе: {request.user.balance} ₽')
                return redirect('my_balance')

            # Создаем комбо-набор
            combo_set = ComboSet.objects.create(
                name=name,
                description=description,
                created_by=request.user,
                total_price=single_price,  # Цена за один заказ
                is_active=True,
                max_orders=max_orders,
                orders_used=0
            )

            # Добавляем блюда в набор
            for item in cart_items:
                ComboItem.objects.create(combo_set=combo_set, dish=item['dish'], quantity=item['quantity'])

            # Списание средств за ВСЕ заказы заранее
            if request.user.deduct_balance(total_price, description=f"Предоплата комбо-набора '{name}' (x{max_orders} заказов)"):
                Payment.objects.create(
                    user=request.user,
                    amount=total_price,
                    status='paid',
                    payment_method='balance',
                    completed_at=timezone.now(),
                    description=f"Предоплата комбо-набора '{name}' (x{max_orders} заказов)"
                )
                
                # Создаем транзакцию
                Transaction.objects.create(
                    user=request.user,
                    amount=total_price,
                    transaction_type='payment',
                    balance_after=request.user.balance,
                    description=f"Предоплата комбо-набора '{name}' (x{max_orders} заказов)",
                    order=None  # Без привязки к конкретному заказу
                )

            messages.success(request, f'Комбо-набор "{name}" создан! Оплачено {total_price} ₽ за {max_orders} заказов.')
            return redirect('my_combo_sets')

        except Exception as e:
            messages.error(request, f'Ошибка создания набора: {str(e)}')
            return redirect('view_cart')

    cart = request.session.get('cart', {})
    cart_items = []
    single_price = 0

    for dish_id_str, quantity in cart.items():
        try:
            dish_id = int(dish_id_str)
            dish = Dish.objects.get(id=dish_id)
            item_total = dish.price * quantity
            cart_items.append({'dish': dish, 'quantity': quantity, 'total': item_total})
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


@login_required
def my_combo_sets(request):
    # Список комбо-наборов пользователя с остатками заказов
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут создавать комбо-наборы')
        return redirect('menu')

    combo_sets = ComboSet.objects.filter(
        created_by=request.user,
        is_active=True
    ).prefetch_related('items__dish').order_by('-created_at')

    # Проверяем доступность каждого набора
    for combo_set in combo_sets:
        combo_set.can_order_now = check_combo_availability(combo_set)

    return render(request, 'orders/my_combo_sets.html', {'combo_sets': combo_sets})


def check_combo_availability(combo_set):
    #Проверяет, можно ли прямо сейчас заказать этот комбо-набор (достаточно ли готовых блюд)
    
    for combo_item in combo_set.items.all():
        prepared_dishes = PreparedDish.objects.filter(dish=combo_item.dish, quantity__gt=0)
        total_available = sum(pd.quantity for pd in prepared_dishes)
        
        if total_available < combo_item.quantity:
            return False
    return True


@login_required
def order_combo_set(request, combo_id):
    # Забрать один заказ из предоплаченного комбо-набора
    combo_set = get_object_or_404(ComboSet, id=combo_id, is_active=True)

    if combo_set.remaining_orders <= 0:
        messages.error(request, 'Лимит заказов этого набора исчерпан')
        return redirect('my_combo_sets')

    if combo_set.created_by != request.user:
        messages.error(request, 'Вы не можете заказать этот набор')
        return redirect('my_combo_sets')

    # Проверяем наличие готовых блюд
    unavailable_items = []
    for combo_item in combo_set.items.all():
        prepared_dishes = PreparedDish.objects.filter(dish=combo_item.dish, quantity__gt=0)
        total_available = sum(pd.quantity for pd in prepared_dishes)
        
        if total_available < combo_item.quantity:
            unavailable_items.append({
                'dish': combo_item.dish.name,
                'required': combo_item.quantity,
                'available': total_available
            })

    if unavailable_items:
        error_msg = "Недостаточно готовых блюд:<br>"
        for item in unavailable_items:
            error_msg += f"- {item['dish']}: нужно {item['required']}, доступно {item['available']}<br>"
        messages.error(request, error_msg)
        return redirect('my_combo_sets')

    try:
        # Создаем обычный заказ (но БЕЗ оплаты - уже предоплачено!)
        order = Order.objects.create(
            customer=request.user,
            status='pending',  # Ожидает получения
            total_price=combo_set.total_price,  # Для информации
            notes=f"Комбо-набор: {combo_set.name} (заказ {combo_set.orders_used + 1}/{combo_set.max_orders})",
            is_visible_to_customer=True
        )

        # Добавляем блюда в заказ и резервируем из готовых
        for combo_item in combo_set.items.all():
            # Создаем элемент заказа
            OrderItem.objects.create(
                order=order,
                dish=combo_item.dish,
                quantity=combo_item.quantity,
                price_at_time=combo_item.dish.price,
                status='ready'  # Готово к выдаче
            )
            
            # Резервируем готовые блюда
            remaining_quantity = combo_item.quantity
            prepared_dishes = PreparedDish.objects.filter(
                dish=combo_item.dish, 
                quantity__gt=0
            ).order_by('prepared_at')  # Берем более старые блюда сначала
            
            for prepared_dish in prepared_dishes:
                if remaining_quantity <= 0:
                    break
                    
                if prepared_dish.quantity >= remaining_quantity:
                    prepared_dish.quantity -= remaining_quantity
                    prepared_dish.save()
                    remaining_quantity = 0
                else:
                    remaining_quantity -= prepared_dish.quantity
                    prepared_dish.quantity = 0
                    prepared_dish.save()

        # Создаем запись о заказе комбо-набора
        ComboOrder.objects.create(
            combo_set=combo_set,
            customer=request.user,
            status='ready',  # Готов к выдаче
            main_order=order
        )

        # Увеличиваем счетчик использованных заказов
        combo_set.increment_usage()

        messages.success(request, f'Заказ #{order.id} из набора "{combo_set.name}" создан! Осталось заказов: {combo_set.remaining_orders}. Забрать можно прямо сейчас.')
        return redirect('view_order', order_id=order.id)

    except Exception as e:
        messages.error(request, f'Ошибка создания заказа: {str(e)}')
        return redirect('my_combo_sets')


@login_required
def take_combo_order(request, order_id):
    # Получить заказ из комбо-набора
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    # Проверяем, что это заказ из комбо-набора
    if not order.notes.startswith('Комбо-набор:'):
        messages.error(request, 'Это не заказ из комбо-набора')
        return redirect('view_order', order_id=order.id)
    
    if order.status != 'pending':
        messages.error(request, 'Заказ уже получен или отменен')
        return redirect('view_order', order_id=order.id)
    
    # Создаем запись о получении
    OrderPickup.objects.create(
        order=order,
        picked_up_by=request.user
    )
    
    # Меняем статус заказа
    order.status = 'picked_up'
    order.save()
    
    # Обновляем статус комбо-заказа
    try:
        combo_order = ComboOrder.objects.get(main_order=order)
        combo_order.status = 'picked_up'
        combo_order.save()
    except ComboOrder.DoesNotExist:
        pass
    
    messages.success(request, f'Заказ #{order.id} получен! Приятного аппетита!')
    return redirect('order_history')


@login_required
def my_combo_orders(request):
    # История заказов комбо-наборов пользователя
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут заказывать комбо-наборы')
        return redirect('menu')

    combo_orders = ComboOrder.objects.filter(customer=request.user).select_related(
        'combo_set', 'main_order'
    ).order_by('-created_at')

    return render(request, 'orders/my_combo_orders.html', {'combo_orders': combo_orders})


@login_required
def cancel_combo_order(request, order_id):
    # Отмена одного заказа из комбо-набора
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status != 'pending':
        messages.error(request, 'Нельзя отменить заказ в текущем статусе')
        return redirect('view_order', order_id=order.id)
    
    try:
        # Возвращаем блюда обратно в готовые
        for order_item in order.items.all():
            prepared_dish, created = PreparedDish.objects.get_or_create(
                dish=order_item.dish,
                defaults={'quantity': order_item.quantity}
            )
            
            if not created:
                prepared_dish.quantity += order_item.quantity
                prepared_dish.save()
        
        # Уменьшаем счетчик использованных заказов в комбо-наборе
        try:
            combo_order = ComboOrder.objects.get(main_order=order)
            combo_set = combo_order.combo_set
            
            # Увеличиваем оставшееся количество заказов
            if combo_set.orders_used > 0:
                combo_set.orders_used -= 1
                combo_set.is_active = True  # Возвращаем активность
                combo_set.save()
            
            # Удаляем запись о комбо-заказе
            combo_order.delete()
        except ComboOrder.DoesNotExist:
            pass
        
        # Отменяем заказ
        order.status = 'cancelled'
        order.is_visible_to_customer = False
        order.save()
        
        messages.success(request, 'Заказ отменен. Остаток заказов в наборе восстановлен.')
        return redirect('my_combo_sets')
        
    except Exception as e:
        messages.error(request, f'Ошибка при отмене заказа: {str(e)}')
        return redirect('view_order', order_id=order.id)


@login_required
def cancel_combo_set(request, combo_id):
    # Полная отмена всего комбо-набора с возвратом средств
    combo_set = get_object_or_404(ComboSet, id=combo_id, created_by=request.user)
    
    if combo_set.orders_used > 0:
        messages.error(request, 'Нельзя отменить набор, из которого уже брали заказы')
        return redirect('my_combo_sets')
    
    try:
        # Рассчитываем сумму для возврата
        total_refund = combo_set.total_price * combo_set.max_orders
        
        # Возвращаем средства
        request.user.add_balance(
            total_refund,
            description=f"Возврат предоплаты за комбо-набор '{combo_set.name}'"
        )
        
        # Создаем транзакцию возврата
        Transaction.objects.create(
            user=request.user,
            amount=total_refund,
            transaction_type='refund',
            balance_after=request.user.balance,
            description=f"Возврат предоплаты за комбо-набор '{combo_set.name}'"
        )
        
        # Удаляем комбо-набор
        combo_set.delete()
        
        messages.success(request, f'Комбо-набор отменен. Средства ({total_refund} ₽) возвращены на баланс.')
        return redirect('my_combo_sets')
        
    except Exception as e:
        messages.error(request, f'Ошибка при отмене набора: {str(e)}')
        return redirect('my_combo_sets')


# Для просмотра доступных комбо-заказов (для информации)
@login_required
def available_combo_orders(request):
    # Показывает все заказы из комбо-наборов, которые готовы к выдаче
    if not request.user.is_student():
        messages.error(request, 'Только ученики могут просматривать заказы')
        return redirect('menu')

    # Ищем заказы в статусе 'pending' с пометкой о комбо-наборе
    combo_orders = Order.objects.filter(
        customer=request.user,
        status='pending',
        notes__startswith='Комбо-набор:'
    ).order_by('created_at')

    return render(request, 'orders/available_combo_orders.html', {'combo_orders': combo_orders})


#  РАБОТА ПОВАРА 

@login_required
def chef_orders(request):
    # Заказы для повара (которые нужно приготовить)
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    orders = Order.objects.filter(status='preparing').select_related('customer').prefetch_related('items__dish__ingredients__ingredient', 'customer__allergens').order_by('created_at')
    
    return render(request, 'orders/chef_orders.html', {'orders': orders})


@login_required
def update_order_status(request, order_id):
    # Изменение статуса заказа
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
            return redirect('manage_orders')
    
    return redirect('menu')


@login_required
def chef_inventory(request):
    # Страница управления запасами для повара
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    ingredients_without_stock = Ingredient.objects.filter(stock__isnull=True)
    for ingredient in ingredients_without_stock:
        IngredientStock.objects.create(
            ingredient=ingredient,
            current_quantity=0,
            min_quantity=10,
            unit=ingredient.unit
        )
        messages.info(request, f'Создан запас для ингредиента: {ingredient.name}')
    
    stocks = IngredientStock.objects.all().select_related('ingredient').order_by('ingredient__name')
    
    total_stocks = stocks.count()
    low_stock_count = stocks.filter(
        models.Q(current_quantity__lte=models.F('min_quantity')) &
        models.Q(current_quantity__gt=0)
    ).count()
    out_of_stock_count = stocks.filter(current_quantity__lte=0).count()
    
    context = {
        'stocks': stocks,
        'total_stocks': total_stocks,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'orders/chef_inventory.html', context)


@login_required
def request_restock(request, ingredient_id):
    # Отправка запроса на пополнение ингредиента
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        notes = request.POST.get('notes', '')
        
        try:
            quantity = Decimal(quantity)
            if quantity <= 0:
                messages.error(request, 'Количество должно быть положительным')
                return redirect('chef_inventory')
            
            stock = ingredient.stock
            
            StockHistory.objects.create(
                ingredient=ingredient,
                operation_type='request',
                quantity_change=quantity,
                quantity_before=stock.current_quantity,
                quantity_after=stock.current_quantity,
                performed_by=request.user,
                notes=f"Запрос на пополнение: {notes}"
            )
            
            messages.success(request, f'Запрос на пополнение {ingredient.name} ({quantity} {ingredient.unit}) отправлен администратору')
            
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректное количество')
    
    return redirect('chef_inventory')


@login_required
def chef_prepare_dishes(request):
    # Страница приготовления блюд поваром
    if not request.user.is_chef():
        messages.error(request, 'Доступно только для поваров')
        return redirect('menu')
    
    dishes_to_prepare = Dish.objects.all()
    prepared_dishes = PreparedDish.objects.all().select_related('dish')
    
    low_stock_count = IngredientStock.objects.filter(current_quantity__lte=models.F('min_quantity')).count()
    out_of_stock_count = IngredientStock.objects.filter(current_quantity__lte=0).count()
    
    if request.method == 'POST':
        dish_id = request.POST.get('dish_id')
        quantity = request.POST.get('quantity')
        
        if dish_id and quantity:
            try:
                dish = Dish.objects.get(id=dish_id)
                quantity = int(quantity)
                
                if quantity <= 0:
                    messages.error(request, 'Количество должно быть положительным')
                    return redirect('chef_prepare_dishes')
                
                missing = dish.check_availability(quantity)
                
                success, _ = dish.reserve_ingredients(quantity, request.user)
                if success:
                    prepared_dish, created = PreparedDish.objects.get_or_create(
                        dish=dish,
                        defaults={'quantity': quantity, 'prepared_by': request.user}
                    )
                    if not created:
                        prepared_dish.quantity += quantity
                        prepared_dish.prepared_by = request.user
                        prepared_dish.save()
                        
                    messages.success(request, f'Приготовлено {quantity} порций {dish.name}')
                else:
                    messages.error(request, f'Ошибка при резервировании ингредиентов')
                missing_list = ", ".join([f"{m['ingredient'].name} (не хватает {m['missing']} {m['ingredient'].unit})" for m in missing])
                messages.error(request, f'Не хватает ингредиентов для {dish.name}: {missing_list}')
                    
            except (ValueError, Dish.DoesNotExist):
                messages.error(request, 'Ошибка в данных')
    
    context = {
        'dishes_to_prepare': dishes_to_prepare,
        'prepared_dishes': prepared_dishes,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'orders/chef_prepare_dishes.html', context)


#  УПРАВЛЕНИЕ БЛЮДАМИ 

@login_required
def manage_dishes(request):
    # Управление блюдами
    if not (request.user.is_admin() or request.user.is_chef()):
        messages.error(request, 'Доступно только для администраторов и поваров')
        return redirect('menu')
    
    dishes = Dish.objects.all().select_related('category')
    categories = Category.objects.all()
    
    return render(request, 'orders/manage_dishes.html', {'dishes': dishes, 'categories': categories})


@login_required
def add_dish(request):
    # Добавление нового блюда
    if not (request.user.is_admin() or request.user.is_chef()):
        raise PermissionDenied("Только для администраторов и поваров")

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        category_id = request.POST.get('category')
        
        image = request.FILES.get('image')

        try:
            category = Category.objects.get(id=category_id)
            dish = Dish.objects.create(
                name=name,
                description=description,
                price=price,
                category=category,
                image=image,
                created_by=request.user
            )

            ingredients = request.POST.getlist('ingredient')
            quantities = request.POST.getlist('quantity')
            for ing_id, qty in zip(ingredients, quantities):
                if ing_id and qty:
                    DishIngredient.objects.create(dish=dish, ingredient_id=ing_id, quantity=qty)

            messages.success(request, f'Блюдо "{dish.name}" и ингредиенты добавлены!')
            return redirect('manage_dishes')

        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')

    categories = Category.objects.all()
    ingredients = Ingredient.objects.all()
    return render(request, 'orders/add_dish.html', {'categories': categories, 'ingredients': ingredients})


@login_required
def edit_dish(request, dish_id):
    # Редактирование существующего блюда
    if not (request.user.is_admin() or request.user.is_chef()):
        raise PermissionDenied("Только для администраторов и поваров")

    dish = get_object_or_404(Dish, id=dish_id)

    if request.method == 'POST':
        dish.name = request.POST.get('name')
        dish.description = request.POST.get('description')
        dish.category_id = request.POST.get('category')

        if request.user.is_admin():
            dish.price = request.POST.get('price')

        if request.FILES.get('image'):
            dish.image = request.FILES.get('image')
        dish.save()

        DishIngredient.objects.filter(dish=dish).delete()
        ingredients = request.POST.getlist('ingredient')
        quantities = request.POST.getlist('quantity')
        for ing_id, qty in zip(ingredients, quantities):
            if ing_id and qty:
                DishIngredient.objects.create(dish=dish, ingredient_id=ing_id, quantity=qty)

        messages.success(request, f'Блюдо "{dish.name}" и ингредиенты обновлены!')
        return redirect('manage_dishes')

    categories = Category.objects.all()
    ingredients = Ingredient.objects.all()
    existing_ingredients = dish.ingredients.all()
    return render(request, 'orders/edit_dish.html', {
        'dish': dish,
        'categories': categories,
        'ingredients': ingredients,
        'existing_ingredients': existing_ingredients
    })


@login_required
def update_dish_image(request, dish_id):
    # Обновление только изображения блюда
    if not (request.user.is_admin() or request.user.is_chef()):
        messages.error(request, 'Только для администраторов и поваров')
        return redirect('manage_dishes')

    dish = get_object_or_404(Dish, id=dish_id)
    
    if request.method == 'POST':
        if request.FILES.get('image'):
            dish.image = request.FILES['image']
            dish.save()
            messages.success(request, f'Изображение для блюда "{dish.name}" обновлено!')
        else:
            messages.error(request, 'Файл изображения не выбран')
    
    return redirect('manage_dishes')


@login_required
def add_ingredient(request):
    # Добавление нового ингредиента
    if not (request.user.is_admin() or request.user.is_chef()):
        raise PermissionDenied("Только для администраторов и поваров")

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        unit = request.POST.get('unit', '').strip()
        if name and unit:
            obj, created = Ingredient.objects.get_or_create(
                name__iexact=name,
                defaults={'name': name, 'unit': unit}
            )
            if created:
                IngredientStock.objects.create(
                    ingredient=obj,
                    current_quantity=0,
                    unit=unit
                )
                messages.success(request, f'Ингредиент «{obj.name}» добавлен.')
            else:
                messages.warning(request, 'Такой ингредиент уже есть.')
        else:
            messages.error(request, 'Заполните оба поля.')
        return redirect('manage_dishes')

    return redirect('manage_dishes')


#  АДМИНИСТРАТИВНЫЕ ФУНКЦИИ 

@login_required
def manage_users(request):
    # Управление пользователями
    if not request.user.is_admin():
        raise PermissionDenied("Только для администраторов")

    users = CustomUser.objects.all()
    return render(request, 'orders/manage_users.html', {'users': users})


@login_required
def change_user_role(request, user_id):
    # Изменение роли пользователя
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
def manage_orders(request):
    # Управление заказами
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')

    orders_list = Order.objects.all().select_related('customer').prefetch_related('items__dish').order_by('-created_at')
    
    total_orders = Order.objects.count()
    active_orders = Order.objects.exclude(status__in=['delivered', 'picked_up', 'cancelled']).count()
    completed_orders = Order.objects.filter(status__in=['delivered', 'picked_up']).count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    
    page = request.GET.get('page', 1)
    paginator = Paginator(orders_list, 20)
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    
    context = {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'total_orders': total_orders,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
    }
    return render(request, 'orders/manage_orders.html', context)


@login_required
def mark_as_paid(request, order_id):
    # Отметка заказа как оплаченного
    if not request.user.is_admin():
        messages.error(request, 'Только администратор')
        return redirect('menu')
    
    order = get_object_or_404(Order, id=order_id)
    
    Payment.objects.create(
        order=order,
        user=order.customer,
        amount=order.total_price,
        status='paid',
        completed_at=timezone.now()
    )
    
    messages.success(request, f'Заказ #{order.id} отмечен как оплаченный')
    return redirect('statistics')


@login_required
def statistics(request):
    # Статистика для администратора
    if not request.user.is_admin():
        messages.error(request, 'Только для администраторов')
        return redirect('menu')
    
    today = timezone.now().date()
    
    try:
        total_users = CustomUser.objects.count()
        total_students = CustomUser.objects.filter(role='student').count()
        total_chefs = CustomUser.objects.filter(role='chef').count()
        total_admins = CustomUser.objects.filter(role='admin').count()

        recent_users = CustomUser.objects.all().order_by('-date_joined')[:10]

        total_payments = Payment.objects.filter(status='paid')
        total_income = total_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        today_payments = Payment.objects.filter(status='paid', created_at__date=today)
        today_income = today_payments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        restock_history = StockHistory.objects.filter(operation_type='restock')
        total_ingredient_cost = restock_history.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0')
        
        today_restock_history = StockHistory.objects.filter(operation_type='restock', created_at__date=today)
        today_ingredient_cost = today_restock_history.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0')
        
        today_logged_users = CustomUser.objects.filter(last_login__date=today).order_by('-last_login')
        
        low_stock_count = IngredientStock.objects.filter(current_quantity__lte=models.F('min_quantity')).count()
        out_of_stock_count = IngredientStock.objects.filter(current_quantity__lte=0).count()
        
        profit = total_income - total_ingredient_cost
        
        context = {
            'total_users': total_users,
            'total_students': total_students,
            'total_chefs': total_chefs,
            'total_admins': total_admins,
            'recent_users': recent_users,
            'today_logged_users': today_logged_users,
            'today_logins': today_logged_users.count(),
            
            'total_income': total_income,
            'today_income': today_income,
            'total_payments': total_payments.count(),
            'today_payments': today_payments.count(),
            
            'total_ingredient_cost': total_ingredient_cost,
            'today_ingredient_cost': today_ingredient_cost,
            'profit': profit,
            
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
        }
        
    except Exception as e:
        messages.error(request, f'Ошибка загрузки статистики: {str(e)}')
        context = {}
    
    return render(request, 'orders/statistics.html', context)


@login_required
def manage_inventory(request):
    # Управление запасами
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    stocks = IngredientStock.objects.all().select_related('ingredient').order_by('ingredient__name')
    
    restock_requests = StockHistory.objects.filter(operation_type='request').select_related('ingredient', 'performed_by').order_by('-created_at')
    
    total_ingredient_cost = StockHistory.objects.filter(operation_type='restock').aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0')
    
    today = timezone.now().date()
    today_ingredient_cost = StockHistory.objects.filter(operation_type='restock', created_at__date=today).aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0')
    
    context = {
        'stocks': stocks,
        'restock_requests': restock_requests,
        'total_ingredient_cost': total_ingredient_cost,
        'today_ingredient_cost': today_ingredient_cost,
    }
    return render(request, 'orders/manage_inventory.html', context)


@login_required
def restock_ingredient(request, stock_id):
    # Пополнение запасов ингредиента с учетом стоимости
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    stock = get_object_or_404(IngredientStock, id=stock_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        cost_per_unit = request.POST.get('cost_per_unit')
        notes = request.POST.get('notes', '')
        
        try:
            quantity = Decimal(quantity)
            cost_per_unit = Decimal(cost_per_unit)
            
            if quantity > 0 and cost_per_unit >= 0:
                old_quantity = stock.current_quantity
                stock.current_quantity += quantity
                stock.last_restocked = timezone.now()
                stock.save()
                
                ingredient_cost, created = IngredientCost.objects.get_or_create(
                    ingredient=stock.ingredient,
                    defaults={'cost_per_unit': cost_per_unit}
                )
                if not created:
                    ingredient_cost.cost_per_unit = cost_per_unit
                    ingredient_cost.save()
                
                total_cost = quantity * cost_per_unit
                
                StockHistory.objects.create(
                    ingredient=stock.ingredient,
                    operation_type='restock',
                    quantity_change=quantity,
                    quantity_before=old_quantity,
                    quantity_after=stock.current_quantity,
                    total_cost=total_cost,
                    performed_by=request.user,
                    notes=f"Пополнение: {notes}"
                )
                
                messages.success(request,
                                 f'Запас {stock.ingredient.name} пополнен на {quantity:.0f} {stock.unit}. '
                                 f'Стоимость: {total_cost:.2f} руб. ({cost_per_unit:.2f} руб/{stock.unit})'.replace('.', ','))
            else:
                messages.error(request, 'Количество и стоимость должны быть положительными')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректные данные')
    
    return redirect('manage_inventory')


@login_required
def fulfill_restock_request(request, request_id):
    # Выполнение запроса на пополнение от повара
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    restock_request = get_object_or_404(StockHistory, id=request_id, operation_type='request')
    
    if request.method == 'POST':
        cost_per_unit = request.POST.get('cost_per_unit')
        notes = request.POST.get('notes', '')
        
        if not cost_per_unit:
            messages.error(request, 'Необходимо указать стоимость за единицу')
            return redirect('manage_inventory')
        
        try:
            quantity = restock_request.quantity_change
            cost_per_unit = Decimal(cost_per_unit)
            
            if cost_per_unit >= 0:
                stock = restock_request.ingredient.stock
                old_quantity = stock.current_quantity
                stock.current_quantity += quantity
                stock.last_restocked = timezone.now()
                stock.save()
                
                ingredient_cost, created = IngredientCost.objects.get_or_create(
                    ingredient=stock.ingredient,
                    defaults={'cost_per_unit': cost_per_unit}
                )
                if not created:
                    ingredient_cost.cost_per_unit = cost_per_unit
                    ingredient_cost.save()
                
                total_cost = quantity * cost_per_unit
                
                restock_request.total_cost = total_cost
                restock_request.notes += f" | Выполнено: {notes}"
                restock_request.save()
                
                StockHistory.objects.create(
                    ingredient=stock.ingredient,
                    operation_type='restock',
                    quantity_change=quantity,
                    quantity_before=old_quantity,
                    quantity_after=stock.current_quantity,
                    total_cost=total_cost,
                    performed_by=request.user,
                    notes=f"Выполнение запроса #{request_id}: {notes}"
                )
                
                messages.success(request,
                                 f'Запрос на пополнение {stock.ingredient.name} выполнен. '
                                 f'Затраты: {total_cost:.2f} руб. ({cost_per_unit:.2f} руб/{stock.unit})'.replace('.', ','))
            else:
                messages.error(request, 'Стоимость должна быть неотрицательной')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректная стоимость')
        except Exception as e:
            messages.error(request, f'Ошибка выполнения запроса: {str(e)}')
    
    return redirect('manage_inventory')


@login_required
def delete_restock_request(request, request_id):
    # Удаление запроса на пополнение без выполнения
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    restock_request = get_object_or_404(StockHistory, id=request_id, operation_type='request')
    
    try:
        ingredient_name = restock_request.ingredient.name
        restock_request.delete()
        messages.success(request, f'Запрос на пополнение {ingredient_name} удален.')
    except Exception as e:
        messages.error(request, f'Ошибка удаления запроса: {str(e)}')
    
    return redirect('manage_inventory')


@login_required
def update_ingredient_cost(request, ingredient_id):
    # Обновление стоимости ингредиента
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    
    if request.method == 'POST':
        cost_per_unit = request.POST.get('cost_per_unit')
        notes = request.POST.get('notes', '')
        
        try:
            cost_per_unit = Decimal(cost_per_unit)
            
            if cost_per_unit >= 0:
                ingredient_cost, created = IngredientCost.objects.update_or_create(
                    ingredient=ingredient,
                    defaults={
                        'cost_per_unit': cost_per_unit,
                        'last_updated': timezone.now()
                    }
                )
                
                StockHistory.objects.create(
                    ingredient=ingredient,
                    operation_type='adjustment',
                    quantity_change=0,
                    quantity_before=ingredient.stock.current_quantity,
                    quantity_after=ingredient.stock.current_quantity,
                    total_cost=0,
                    performed_by=request.user,
                    notes=f"Изменение стоимости: {cost_per_unit} руб/{ingredient.unit}. {notes}"
                )
                
                messages.success(request, 
                    f'Стоимость {ingredient.name} обновлена: {cost_per_unit} руб/{ingredient.unit}')
            else:
                messages.error(request, 'Стоимость должна быть неотрицательной')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректная стоимость')
    
    return redirect('manage_inventory')


@login_required
def adjust_stock(request, stock_id):
    # Корректировка запасов ингредиента
    if not request.user.is_admin():
        messages.error(request, 'Доступно только для администраторов')
        return redirect('menu')
    
    stock = get_object_or_404(IngredientStock, id=stock_id)
    
    if request.method == 'POST':
        new_quantity = request.POST.get('new_quantity')
        notes = request.POST.get('notes', '')
        
        try:
            new_quantity = Decimal(new_quantity)
            if new_quantity >= 0:
                old_quantity = stock.current_quantity
                change = new_quantity - old_quantity
                
                stock.current_quantity = new_quantity
                stock.save()
                
                StockHistory.objects.create(
                    ingredient=stock.ingredient,
                    operation_type='adjustment',
                    quantity_change=change,
                    quantity_before=old_quantity,
                    quantity_after=new_quantity,
                    performed_by=request.user,
                    notes=notes
                )
                
                messages.success(request, 
                    f'Запас {stock.ingredient.name} скорректирован: {old_quantity} → {new_quantity} {stock.unit}')
            else:
                messages.error(request, 'Количество не может быть отрицательным')
        except (ValueError, InvalidOperation):
            messages.error(request, 'Некорректное количество')
    
    return redirect('manage_inventory')
