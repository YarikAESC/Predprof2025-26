from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import RegistrationForm, LoginForm, ProfileEditForm
from django.http import HttpResponse
from .models import CustomUser

def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('profile')
        else:
            messages.error(request, 'Исправьте ошибки в форме')
    else:
        form = RegistrationForm()
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, 'Вход выполнен успешно!')
                return redirect('profile')
            else:
                messages.error(request, 'Неверный логин или пароль')
    else:
        form = LoginForm()
    
    return render(request, 'users/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('login')

@login_required
def profile_view(request):
    return render(request, 'users/profile.html', {'user': request.user})

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileEditForm(
            request.POST, 
            request.FILES, 
            instance=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль обновлен успешно!')
            return redirect('profile')
        else:
            messages.error(request, 'Исправьте ошибки в форме')
    else:
        form = ProfileEditForm(instance=request.user)
    
    return render(request, 'users/edit_profile.html', {'form': form})

@login_required
def user_list(request):
    """Список пользователей"""
    users = CustomUser.objects.all()
    return render(request, 'users/user_list.html', {'users': users})

@login_required
def user_detail(request, user_id=None):
    """Детальная информация о пользователе"""
    if user_id:
        user = get_object_or_404(CustomUser, id=user_id)
    else:
        user = request.user
    
    return render(request, 'users/user_detail.html', {'user': user})
def index(request):
    """Главная страница приложения users"""
    html = """
    <h1>Приложение Users</h1>
    <p>Приложение для работы с пользователями</p>
    <ul>
        <li><a href="/users/list/">Список пользователей</a></li>
        <li><a href="/users/detail/">Профиль пользователя</a></li>
        <li><a href="/admin/">Админка</a></li>
    </ul>
    """
    return HttpResponse(html)
