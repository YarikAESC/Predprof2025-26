from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Основные URL пользователей
    path('', views.profile_view, name='profile'),  # Главная страница профиля
    path('register/', views.register_view, name='register'),  # Регистрация
    path('login/', views.login_view, name='login'),  # Вход
    path('logout/', views.logout_view, name='logout'),  # Выход
    path('list/', views.user_list, name='user_list'),  # Список всех пользователей
    path('detail/<int:user_id>/', views.user_detail, name='user_detail'),  # Профиль другого пользователя
    path('detail/', views.user_detail, name='user_detail_self'),  # Свой профиль
    path('edit/', views.edit_profile, name='edit_profile'),  # Редактирование профиля
    
    # URL для восстановления пароля
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt',
             success_url='/users/password-reset/done/'
         ), 
         name='password_reset'),  # Запрос сброса пароля
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),  # Подтверждение отправки письма
    
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),  # Ввод нового пароля
    
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ),
         name='password_reset_complete'),  # Подтверждение смены пароля
]

