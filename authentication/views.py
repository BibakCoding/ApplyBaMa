from django.contrib import messages
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
    get_user_model,
)
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit

from .forms import (
    LoginForm,
    RegisterForm,
    ConfirmCodeForm,
    PasswordResetRequestForm,
    ChangePasswordForm,
)
from .models import VerificationCode
from .tasks import send_async_email

User = get_user_model()



def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def dispatch_email(subject, template_name, context, to):
    try:
        send_async_email.delay(subject, template_name, context, to)
        return True
    except:
        return False


# Login
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            auth_login(request, form.user)
            msg = _("Logged in successfully.")
            if is_ajax(request):
                return JsonResponse(
                    {"success": True, "message": msg, "redirect": reverse("dashboard")}
                )
            messages.success(request, msg)
            return redirect("dashboard")

        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for err in form.non_field_errors():
            messages.error(request, err)

    return render(request, "authentication/login.html", {"form": form})


# Register
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def register_view(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            user, created = User.objects.get_or_create(
                email=email, defaults={"username": email, "is_active": False}
            )
            if created:
                user.set_password(form.cleaned_data["password1"])
                user.save()

            # Issue registration code
            vc = VerificationCode.create_registration(user)

            dispatch_email(
                subject=_("Your Confirmation Code"),
                template_name="emails/confirmation_code.html",
                context={"code": vc.code, "site_name": "Apply Ba Ma"},
                to=[email],
            )

            messages.success(
                request, _("We sent you an email that includes verification code.")
            )
            redirect_url = reverse("confirm_code", kwargs={"pk": user.pk})
            if is_ajax(request):
                return JsonResponse({"success": True, "redirect": redirect_url})
            return redirect(redirect_url)

        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for field, errs in form.errors.items():
            if field != "__all__":
                for e in errs:
                    messages.error(request, f"{form.fields[field].label}: {e}")
        for e in form.non_field_errors():
            messages.error(request, e)

    return render(request, "authentication/register.html", {"form": form})


# Logout
def logout_view(request):
    auth_logout(request)
    messages.success(request, _("You have logged out."))
    return redirect("main")


# Confirm Code
def confirm_code(request, pk):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    user = get_object_or_404(User, pk=pk)
    vc = VerificationCode.objects.filter(
        user=user, code_type=VerificationCode.CodeType.REGISTRATION
    ).first()

    if not vc or vc.used:
        msg = _("This confirmation page is no longer valid.")
        if is_ajax(request):
            return JsonResponse(
                {"success": False, "errors": {"__all__": [{"message": msg}]}},
                status=404,
            )
        messages.error(request, msg)
        return redirect("main")

    form = ConfirmCodeForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            code = form.cleaned_data["code"]
            if vc.expires_at < timezone.now():
                form.add_error(None, _("Your code has expired."))
            elif vc.code != code:
                form.add_error("code", _("Invalid confirmation code."))
            else:
                vc.used = True
                vc.save()
                user.is_active = True
                user.save()
                auth_login(request, user)
                msg = _("Account confirmed!")
                if is_ajax(request):
                    return JsonResponse({"success": True, "redirect": reverse("dashboard")})
                messages.success(request, msg)
                return redirect("dashboard")

        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for err in form.non_field_errors():
            messages.error(request, err)
        for f, errs in form.errors.items():
            if f != "__all__":
                for e in errs:
                    messages.error(request, f"{form.fields[f].label}: {e}")

    return render(
        request, "authentication/confirm_code.html", {"form": form, "user_id": user.pk}
    )


# Resend Code
@ratelimit(key="ip", rate="3/m", method="POST", block=True)
def resend_code(request, pk):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    user = User.objects.filter(pk=pk, is_active=False).first()
    if not user:
        msg = _("User not found or already active.")
        if is_ajax(request):
            return JsonResponse(
                {"success": False, "errors": {"__all__": [{"message": msg}]}},
                status=404,
            )
        messages.error(request, msg)
        return redirect("register")

    # Issue new registration code
    vc = VerificationCode.create_registration(user)

    dispatch_email(
        subject=_("Your new Confirmation Code"),
        template_name="emails/confirmation_code.html",
        context={"code": vc.code, "site_name": "Apply Ba Ma"},
        to=[user.email],
    )
    msg = _("A fresh confirmation code has been sent.")
    if is_ajax(request):
        return JsonResponse({"success": True, "message": msg})
    messages.success(request, msg)

    return redirect("confirm_code", pk=pk)


# Password Reset Request


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def forget_password(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            vc = VerificationCode.create_reset(user)
            reset_url = request.build_absolute_uri(
                reverse("change_password", kwargs={"token": vc.token})
            )
            dispatch_email(
                subject=_("Reset Your Password"),
                template_name="emails/reset_password.html",
                context={
                    "site_name": "Apply Ba Ma",
                    "reset_url": reset_url,
                    "code": vc.code,
                },
                to=[email],
            )
        msg = _("If that email is registered, you’ll receive reset instructions.")
        if is_ajax(request):
            return JsonResponse({"success": True, "message": msg})
        messages.success(request, msg)
        return redirect("main")

    if request.method == "POST":
        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for e in form.non_field_errors():
            messages.error(request, e)

    return render(request, "authentication/forget_password.html", {"form": form})


# Password Change via Token
def change_password(request, token):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect("dashboard")

    vc = VerificationCode.objects.filter(
        token=token,
        code_type=VerificationCode.CodeType.RESET,
        used=False,
        expires_at__gte=timezone.now(),
    ).first()

    if not vc:
        msg = _("Invalid or expired reset link.")
        if is_ajax(request):
            return JsonResponse(
                {"success": False, "errors": {"__all__": [{"message": msg}]}},
                status=404,
            )
        messages.error(request, msg)
        return redirect("login")

    form = ChangePasswordForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            if form.cleaned_data["code"] != vc.code:
                form.add_error("code", _("Invalid verification code."))
            else:
                user = vc.user
                user.set_password(form.cleaned_data["new_password1"])
                user.save()
                vc.used = True
                vc.save()
                msg = _("Password updated successfully.")
                if is_ajax(request):
                    return JsonResponse(
                        {"success": True, "message": msg, "redirect": reverse("login")}
                    )
                messages.success(request, msg)
                return redirect("login")

        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for f, errs in form.errors.items():
            if f == "__all__":
                for e in errs:
                    messages.error(request, e["message"])
            else:
                for e in errs:
                    messages.error(request, f"{form.fields[f].label}: {e['message']}")

    return render(request, "authentication/change_password.html", {"form": form})
