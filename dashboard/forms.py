# dashboard/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import PasswordChangeForm
from core.models import User, StudentProfile, City
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

BASE_INPUT_CLASS = 'ab-input w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--ab-primary)] focus:border-transparent transition-all bg-white'

class PersonalInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'gender', 'date_of_birth', 'father_name', 'mother_name']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('First Name')}),
            'last_name': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Last Name')}),
            'gender': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
            'date_of_birth': forms.DateInput(attrs={'class': BASE_INPUT_CLASS, 'type': 'date'}),
            'father_name': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Father Name')}),
            'mother_name': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Mother Name')}),
        }

class ContactInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'mobile', 'country', 'city']
        widgets = {
            'email': forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Email Address')}),
            'mobile': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Mobile Number')}),
            'country': forms.Select(attrs={
                'class': 'select2-country ' + BASE_INPUT_CLASS,
                'data-placeholder': _('Select a country'),
            }),
            'city': forms.Select(attrs={
                'class': 'select2-city ' + BASE_INPUT_CLASS,
                'data-placeholder': _('Select a city'),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['city'].queryset = City.objects.none()

        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['city'].queryset = City.objects.filter(
                    country_id=country_id
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.country:
            self.fields['city'].queryset = self.instance.country.cities.order_by('name')

class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['profile_image']
        widgets = {
            'profile_image': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-[var(--ab-primary)] hover:file:bg-blue-100'}),
        }

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['passport', 'stage', 'language']
        widgets = {
            'passport': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Passport Number')}),
            'stage': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
            'language': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': BASE_INPUT_CLASS, 'placeholder': _(field.label)})


# Add these to your existing dashboard/forms.py
from core.models import Application, User, StudentProfile

BASE_INPUT_CLASS = 'ab-input w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--ab-primary)] focus:border-transparent transition-all bg-white'

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['student', 'program', 'student_type', 'documents']
        widgets = {
            'student': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
            'program': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
            'student_type': forms.Select(attrs={'class': BASE_INPUT_CLASS}),
            'documents': forms.FileInput(attrs={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-[var(--ab-primary)] hover:file:bg-blue-100'}),
        }

    def __init__(self, *args, **kwargs):
        agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        if agent:
            # Agent only sees students they are currently managing
            student_ids = Application.objects.filter(agent=agent).values_list('student_id', flat=True).distinct()
            self.fields['student'].queryset = User.objects.filter(id__in=student_ids)
        else:
            self.fields['student'].queryset = User.objects.none()


class AddStudentForm(forms.Form):
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('First Name')}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Last Name')}))
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Username')}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Email Address')}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': _('Temporary Password')}))

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError(_('This username is already taken.'))
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_('This email is already registered.'))
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise ValidationError(_('Password must be at least 8 characters long.'))
        return password
