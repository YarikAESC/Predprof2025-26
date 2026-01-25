from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError 

# Получаем модель пользователя
User = get_user_model()

# Форма регистрации пользователя
class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, max_length=30)
    last_name = forms.CharField(required=False, max_length=30)
    phone = forms.CharField(required=False, max_length=20)  # Поле телефона
    birth_date = forms.DateField(
        required=False, 
        label='Дата рождения',
        widget=forms.DateInput(attrs={'type': 'date'})  # Датапикер
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 
                 'phone','birth_date', 'email', 'password1', 'password2']
    
    # Проверка уникальности email
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже существует')
        return email
    
    # Сохранение пользователя
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.phone = self.cleaned_data.get('phone', '')
        user.birth_date = self.cleaned_data.get('birth_date')
        if commit:
            user.save()
        return user

# Форма входа пользователя
class LoginForm(forms.Form):
    username = forms.CharField(
        label='Имя пользователя', 
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label='Пароль', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

# Форма редактирования профиля пользователя
class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'avatar', 'birth_date', 'allergens'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'allergens': forms.CheckboxSelectMultiple()
        }
