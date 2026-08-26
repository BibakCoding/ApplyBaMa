from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from core.models import User


class LoginForm(forms.Form):
    username = forms.CharField(label=_("Email or Username"))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        identifier = cleaned.get("username", "").strip()
        password = cleaned.get("password")

        if not identifier or not password:
            raise forms.ValidationError(
                _("Please enter your email/username and password."),
                code="required",
            )

        # Try email first, then username
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            user = User.objects.filter(username__iexact=identifier).first()

        if user:
            authenticated = authenticate(username=user.username, password=password)
            if authenticated is None:
                raise forms.ValidationError(
                    _("Wrong email/username or password!"),
                    code="invalid_credentials",
                )
            if not user.is_active:
                raise forms.ValidationError(
                    _("Your account is not active. Please verify your email."),
                    code="inactive",
                )
            self.user = authenticated
        else:
            raise forms.ValidationError(
                _("No account found with this email or username."),
                code="not_found",
            )
        return cleaned


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_("Password"), widget=forms.PasswordInput, validators=[validate_password]
    )
    password2 = forms.CharField(label=_("Confirm Password"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email"]
        labels = {"email": _("Email")}

    def clean_email(self):
        email = self.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user is not None and user.is_active == True:
            raise forms.ValidationError(_("Email already in use."))
        return email

    def clean(self):
        super().clean()
        if self.cleaned_data.get("password1") != self.cleaned_data.get("password2"):
            raise forms.ValidationError(_("Passwords do not match."))
        return self.cleaned_data


class ConfirmCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label=_("Confirmation Code"),
        widget=forms.TextInput(attrs={"inputmode": "numeric"}),
    )


class PasswordResetRequestForm(PasswordResetForm):
    email = forms.EmailField(label=_("Email"), max_length=254)


class ChangePasswordForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label=_("Verification Code"),
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "placeholder": "Enter code"}
        ),
    )
    new_password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(attrs={"placeholder": "********"}),
        validators=[validate_password],
    )
    new_password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(attrs={"placeholder": "********"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("new_password1") != cleaned_data.get("new_password2"):
            raise forms.ValidationError(_("Passwords do not match."))
        return cleaned_data
