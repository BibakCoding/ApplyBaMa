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
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import get_language, gettext as _
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
from core.utils.jwt_auth import JWTManager
from core.utils.notifications import send_welcome_notification, send_email_verified_notification

User = get_user_model()

def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def dispatch_email(subject, template_name, context, to):
    try:
        send_async_email.delay(subject, template_name, context, to)
        return True
    except:
        return False

def generate_unique_username(base):
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username

def get_next_target(request):
    """Return the requested post-authentication destination, or "".

    A dashboard deep link (?page=profile, ?page=my_applications, ...) travels as
    Django's standard `next` value. It arrives in the query string when
    @login_required bounces an anonymous visitor, and in the POST body once the
    page's own form submits, so both are checked.

    Only same-host targets are accepted: anything absolute, protocol-relative or
    otherwise pointing off-site is ignored, so a crafted ?next= can never turn
    these forms into an open redirect.
    """
    target = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return ""

def resolve_next_destination(request, fallback="dashboard"):
    """Return the validated destination, falling back to `fallback`.

    Used wherever a view finishes an authentication step and has to decide where
    to send the user, so the deep link chosen before logging in is not lost.
    """
    return get_next_target(request) or reverse(fallback)

def append_next(url, request):
    """Append the validated `next` target to an internal URL, when there is one.

    Keeps the target alive across the multi-step detours (register -> confirm
    code -> username selection), which are separate requests rather than one
    form chain.
    """
    target = get_next_target(request)
    if not target:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'next': target})}"

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

    form = LoginForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = form.user
            remember_me = request.POST.get('remember_me')

            if remember_me:
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)

            # Log in the user (session-based)
            auth_login(request, user)

            msg = _("Logged in successfully.")

            # Generate JWT tokens for API authentication
            access_token = JWTManager.create_access_token(user)
            refresh_token = JWTManager.create_refresh_token(user)

            if is_ajax(request):
                return JsonResponse({
                    "success": True,
                    "message": msg,
                    "redirect": resolve_next_destination(request),
                    "access": access_token,
                    "refresh": refresh_token,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "username": user.username,
                        "user_type": user.user_type,
                        "first_name": user.first_name or "",
                        "last_name": user.last_name or "",
                    }
                })
            messages.success(request, msg)
            return redirect(resolve_next_destination(request))

        errors = form.errors.get_json_data()
        if is_ajax(request):
            return JsonResponse({"success": False, "errors": errors}, status=400)
        for err in form.non_field_errors():
            messages.error(request, err)

    return render(
        request,
        "authentication/login.html",
        {"form": form, "next": get_next_target(request)},
    )

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def register_view(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            email = form.cleaned_data["email"]
            base_username = email.split('@')[0]
            unique_username = generate_unique_username(base_username)

            user, created = User.objects.get_or_create(
                email=email, defaults={"username": unique_username, "is_active": False}
            )
            if created:
                user.set_password(form.cleaned_data["password1"])
                user.save()

            vc = VerificationCode.create_registration(user)

            dispatch_email(
                subject=_("Your Confirmation Code"),
                template_name="emails/confirmation_code.html",
                context={
                    "code": vc.code,
                    "site_name": "Apply Ba Ma",
                    # The email renders in a Celery worker where the request
                    # language is gone, so it travels with the message.
                    "language": get_language(),
                    "site_url": request.build_absolute_uri("/"),
                },
                to=[email],
            )

            messages.success(
                request, _("We sent you an email that includes verification code.")
            )
            # The target is carried into the confirmation step, which in turn
            # hands it to the username step, so a deep link survives the whole
            # registration detour instead of landing on the default page.
            redirect_url = append_next(
                reverse("confirm_code", kwargs={"pk": user.pk}), request
            )
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

    return render(
        request,
        "authentication/register.html",
        {"form": form, "next": get_next_target(request)},
    )

def logout_view(request):
    auth_logout(request)
    messages.success(request, _("You have logged out."))
    return redirect("main")

def confirm_code(request, pk):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

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
                # Registration confirmed the address, so the account starts
                # with a verified email (matches the data backfill).
                user.email_verified = True
                user.save()
                auth_login(request, user)

                # Send welcome notification
                send_welcome_notification(user)

                msg = _("Account confirmed!")
                next_url = append_next(reverse("username_selection"), request)
                if is_ajax(request):
                    return JsonResponse({"success": True, "redirect": next_url})
                messages.success(request, msg)
                return redirect(next_url)

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
        request,
        "authentication/confirm_code.html",
        {"form": form, "user_id": user.pk, "next": get_next_target(request)},
    )

@ratelimit(key="ip", rate="3/m", method="POST", block=True)
def resend_code(request, pk):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

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

    vc = VerificationCode.create_registration(user)

    dispatch_email(
        subject=_("Your new Confirmation Code"),
        template_name="emails/confirmation_code.html",
        context={
            "code": vc.code,
            "site_name": "Apply Ba Ma",
            "language": get_language(),
            "site_url": request.build_absolute_uri("/"),
        },
        to=[user.email],
    )
    msg = _("A fresh confirmation code has been sent.")
    if is_ajax(request):
        return JsonResponse({"success": True, "message": msg})
    messages.success(request, msg)

    return redirect(append_next(reverse("confirm_code", kwargs={"pk": pk}), request))

@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def forget_password(request):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

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
                    "language": get_language(),
                    "site_url": request.build_absolute_uri("/"),
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

def verify_email(request, token):
    """Landing page for an email verification link.

    The link confirms one of two things: a NEW address, when a logged-in user
    requested a change (the pending address is committed onto the account), or
    the CURRENT address, when a never-verified account asked to confirm the
    address it already had (the address is unchanged and the account simply
    leaves read-only mode). Opening it with a live token marks the code used
    and shows a confirmation page; any other state (unknown token, already
    used, expired, or stale with nothing left to activate) renders the same
    page in a failed variant with a way forward.
    """
    vc = VerificationCode.objects.filter(
        token=token,
        code_type=VerificationCode.CodeType.EMAIL_CHANGE,
        used=False,
    ).first()

    if not vc:
        return render(
            request,
            "authentication/verify_email.html",
            {"status": "invalid"},
            status=404,
        )

    if vc.expires_at < timezone.now():
        # The user can simply ask for a new link from their profile, so an
        # expired request is cleaned up here: the pending address is dropped
        # and the account returns to its previous, verified state.
        user = vc.user
        if user.pending_email:
            user.pending_email = None
            user.save(update_fields=["pending_email"])
        vc.used = True
        vc.save()
        return render(
            request,
            "authentication/verify_email.html",
            {"status": "expired"},
            status=410,
        )

    user = vc.user
    new_email = user.pending_email
    if not new_email and user.email_verified:
        # Stale link: the request behind it was already confirmed or cancelled,
        # so there is nothing left to activate. Treated as expired so the
        # profile returns to a clean state.
        vc.used = True
        vc.save()
        return render(
            request,
            "authentication/verify_email.html",
            {"status": "expired"},
            status=410,
        )

    # Whether this link activates a changed address or confirms the address
    # the account already had; only the former is a "new" address.
    is_change = bool(new_email)

    vc.used = True
    vc.save()

    if new_email:
        # A requested change is committed onto the account.
        user.email = new_email
        user.pending_email = None
        user.email_verified = True
        user.save(update_fields=["email", "pending_email", "email_verified"])
    else:
        # No change was requested: the account confirms the address it already
        # has, which is how a never-verified account leaves read-only mode.
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        new_email = user.email

    # A success notification so the dashboard banner clears itself the next
    # time the user loads a page. The plain "verified" wording is used when the
    # address itself did not change (new_email is None for that case).
    send_email_verified_notification(user, new_email=new_email if is_change else None)

    return render(request, "authentication/verify_email.html", {"status": "success", "new_email": new_email})

def change_password(request, token):
    if request.user.is_authenticated:
        messages.info(request, _("You are already logged in."))
        return redirect(resolve_next_destination(request))

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

def username_selection(request):
    if not request.user.is_authenticated:
        return redirect("login")

    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "skip":
            return redirect(resolve_next_destination(request))
        elif action == "save":
            new_username = request.POST.get("username", "").strip()
            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                    msg = _("This username is already taken.")
                    if is_ajax(request):
                        return JsonResponse({"success": False, "errors": {"__all__": [{"message": msg}]}}, status=400)
                    messages.error(request, msg)
                else:
                    user.username = new_username
                    user.save()
                    msg = _("Username updated successfully.")
                    if is_ajax(request):
                        return JsonResponse({"success": True, "redirect": resolve_next_destination(request), "message": msg})
                    messages.success(request, msg)
                    return redirect(resolve_next_destination(request))
            else:
                return redirect(resolve_next_destination(request))

    return render(
        request,
        "authentication/username_selection.html",
        {"next": get_next_target(request)},
    )
