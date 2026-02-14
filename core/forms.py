# core/forms.py
from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import User, City
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ProfileForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'profile_image',
            'gender', 'country', 'city', 'date_of_birth',
            'father_name', 'mother_name', 'citizenship', 'mobile'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind classes to form fields
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            })

        # Special handling for country/city fields
        self.fields['city'].queryset = City.objects.none()

        if 'country' in self.data:
            try:
                country_id = int(self.data.get('country'))
                self.fields['city'].queryset = City.objects.filter(country_id=country_id).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.country:
            self.fields['city'].queryset = self.instance.country.cities.order_by('name')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise ValidationError(_("Username is already taken."))
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError(_("Email is already in use."))
        return email

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image', False)
        if image:
            # File size validation (2MB)
            if image.size > 2 * 1024 * 1024:
                raise ValidationError(_("Image file too large (max 2MB)"))
            return image
        return None