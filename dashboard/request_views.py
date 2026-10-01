"""Representation-request HTTP endpoints.

The Requests page itself is an ordinary SPA fragment (``dashboard_content``,
``content_map["requests"]``); the endpoints here are the JSON calls that page
and the "Add by ID" dialog in "My Students" make.

Authorization is entirely :mod:`core.agent_requests`: the ID lookup only ever
matches a full 16-digit ``User.public_id``, ``can_send_request`` owns the rules
(no self-requests, one live request per pair, no request for a user you already
manage) and ``respond_to_request`` refuses anyone but the target. Nothing here
accepts a client-supplied user id — the target is always re-resolved from the
ID the requester typed, so a forged POST cannot address an account the ID does
not belong to.
"""

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from core import agent_requests
from core.models import AgentLinkRequest, User
from dashboard.views import email_verification_required, login_required

EMAIL_RE = re.compile(r"^([^@]{1,2})[^@]*@(.*)$")


def _error(message, status=400):
    return JsonResponse({"success": False, "message": message}, status=status)


def _masked_email(user):
    """``ab***@example.com`` — enough for the requester to confirm the person.

    The ID is the secret the student chose to share; the directory is not, so
    the lookup confirms an identity instead of disclosing contact details.
    """
    email = user.email or ""
    match = EMAIL_RE.match(email)
    if not match:
        return email
    return f"{match.group(1)}***@{match.group(2)}"


def _candidate_payload(user):
    return {
        "id": user.pk,
        "name": user.get_full_name() or user.username,
        "username": user.username,
        "email": _masked_email(user),
        "role": user.get_user_type_display(),
        "public_id": user.public_id,
    }


def _can_initiate(user):
    """Accounts that represent others — the same gate as the "My Students" page."""
    return bool(
        user.user_type in (User.UserType.AGENT, User.UserType.COMPANY)
        or (user.user_type == User.UserType.DEFAULT and user.is_representative)
    )


@login_required
def search_candidate(request):
    """Look up the account behind a 16-digit ID (JSON, read-only)."""
    if not _can_initiate(request.user):
        return _error(_("Only agents and companies can send representation requests."), 403)

    candidate = agent_requests.find_user_by_public_id(request.GET.get("public_id", ""))
    if candidate is None:
        return JsonResponse(
            {
                "success": True,
                "found": False,
                "can_send": False,
                "message": agent_requests.reason_message("not_found"),
            }
        )

    allowed, reason = agent_requests.can_send_request(request.user, candidate)
    return JsonResponse(
        {
            "success": True,
            "found": True,
            "can_send": allowed,
            "message": "" if allowed else agent_requests.reason_message(reason),
            "candidate": _candidate_payload(candidate),
        }
    )


@login_required
@email_verification_required
@ratelimit(key="user", rate="30/h", method="POST", block=True)
@require_POST
def send_request(request):
    """Send "will you accept me as your agent?" to the account behind the ID."""
    if not _can_initiate(request.user):
        return _error(_("Only agents and companies can send representation requests."), 403)

    candidate = agent_requests.find_user_by_public_id(request.POST.get("public_id", ""))
    allowed, reason = agent_requests.can_send_request(request.user, candidate)
    if not allowed:
        return _error(agent_requests.reason_message(reason))

    try:
        link = agent_requests.send_link_request(
            request.user, candidate, request.POST.get("message", "")
        )
    except IntegrityError:
        # Lost a race with another tab: the live-request constraint is the
        # real guard, and the answer is the same as the pre-check's.
        return _error(agent_requests.reason_message("pending"))

    return JsonResponse(
        {
            "success": True,
            "id": link.pk,
            "message": _(
                "Request sent to %(name)s. They will appear in My Students once they accept."
            )
            % {"name": candidate.get_full_name() or candidate.username},
        }
    )


@login_required
@email_verification_required
@require_POST
def respond_request(request, pk):
    """Accept or decline a request addressed to the acting user."""
    link = AgentLinkRequest.objects.filter(pk=pk, target=request.user).first()
    if link is None:
        return _error(_("Request not found."), 404)

    accepted = request.POST.get("action") == "accept"
    try:
        agent_requests.respond_to_request(link, request.user, accept=accepted)
    except (PermissionError, ValidationError) as exc:
        return _error(" ".join(getattr(exc, "messages", [])) or str(exc))

    if accepted:
        message = _(
            "%(name)s is now one of your agents and you can message them."
        ) % {"name": agent_requests.requester_label(link.requester)}
    else:
        message = _("You declined the representation request.")
    return JsonResponse({"success": True, "status": link.status, "message": message})


@login_required
@email_verification_required
@require_POST
def cancel_request(request, pk):
    """Withdraw a request the acting user sent, while it is still pending."""
    link = AgentLinkRequest.objects.filter(pk=pk, requester=request.user).first()
    if link is None:
        return _error(_("Request not found."), 404)

    try:
        agent_requests.cancel_request(link, request.user)
    except (PermissionError, ValidationError) as exc:
        return _error(" ".join(getattr(exc, "messages", [])) or str(exc))

    return JsonResponse(
        {
            "success": True,
            "status": link.status,
            "message": _("The representation request was withdrawn."),
        }
    )
