from django import forms
from django.contrib.auth.forms import UserChangeForm

from core.models import User, City


class ProfileForm(UserChangeForm):
    # Remove password field
    password = None

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'profile_image',
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
