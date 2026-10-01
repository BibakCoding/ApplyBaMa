"""Representation requests — the consent gate before an account manages a user.

A registered student is not the agent's to add. The permission model reads
ownership off ``Application.agent`` (:func:`dashboard.views.get_managed_students`,
and therefore also the chat framework in :mod:`core.chat`), so that link may
only come into existence with the user's own consent:

1. the user reads their 16-digit ``User.public_id`` and gives it to the agent;
2. the agent looks the ID up and sends an :class:`~core.models.AgentLinkRequest`
   ("Will you accept me as your agent?") with an optional note;
3. the target accepts or declines. **Approval** creates the ``Application``
   link, which is what makes the user appear in "My Students", selectable in
   "New Application" and reachable in chat.

Nothing is ever deleted: declined and cancelled requests stay as a trail, and
the target may change their mind later (a new request is allowed once the
previous one is no longer pending — the database enforces exactly one *live*
request per ordered pair, so a requester cannot spam the same target).

Any account may be the requester and any account may be the target: agents and
companies can themselves be represented by another account. The only excluded
pair is a user requesting themselves.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import AgentLinkRequest, Application, User
from realtime.push import notify_user, push_to_user

# Length of ``User.public_id``; a lookup only ever matches a full-length value.
PUBLIC_ID_LENGTH = 16

# The dashboard page an accepted/declined request notification points at.
REQUESTS_PAGE = "requests"


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def normalize_public_id(raw):
    """Reduce user input to the digits that can make up a public ID.

    The ID is read off a screen and typed (or pasted from a message), so
    spaces, dashes and stray characters are normal; they are simply dropped.
    """
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def find_user_by_public_id(raw):
    """The active account whose public ID matches ``raw``, or None.

    ``raw`` must resolve to exactly :data:`PUBLIC_ID_LENGTH` digits — a partial
    ID never matches, so the endpoint is not a search-as-you-type oracle over
    the user table.
    """
    digits = normalize_public_id(raw)
    if len(digits) != PUBLIC_ID_LENGTH:
        return None
    return User.objects.filter(public_id=digits, is_active=True).first()


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def is_managed_by(account, user):
    """True when ``user`` is already one of ``account``'s students."""
    from dashboard.views import get_managed_students

    return user.pk in set(get_managed_students(account))


def pending_request_between(requester, target):
    """The live request from ``requester`` to ``target``, if there is one."""
    return AgentLinkRequest.objects.filter(
        requester=requester,
        target=target,
        status=AgentLinkRequest.Status.PENDING,
    ).first()


def can_send_request(requester, target):
    """Whether ``requester`` may ask ``target`` to be represented by them.

    Returns ``(allowed, reason)``; reason is one of ``not_found``, ``self``,
    ``inactive``, ``already_managed``, ``pending`` or an empty string when the
    request is allowed.
    """
    if target is None:
        return False, "not_found"
    if target.pk == requester.pk:
        return False, "self"
    if not target.is_active:
        return False, "inactive"
    if is_managed_by(requester, target):
        return False, "already_managed"
    if pending_request_between(requester, target) is not None:
        return False, "pending"
    return True, ""


def reason_message(reason):
    """A translated sentence for a :func:`can_send_request` refusal."""
    messages = {
        "not_found": _(
            "No account matches that ID. Ask the student to check it and try again."
        ),
        "self": _("You cannot send a representation request to yourself."),
        "inactive": _("That account is not active."),
        "already_managed": _("That user is already one of your students."),
        "pending": _("You already have a pending request for that user."),
    }
    return messages.get(reason, _("This request could not be sent."))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def send_link_request(requester, target, message=""):
    """Create the pending request and tell the target about it.

    The unique constraint on live requests is the real guard: a concurrent
    duplicate raises IntegrityError, which the view turns into the same
    "you already have a pending request" answer as the pre-check.
    """
    link = AgentLinkRequest.objects.create(
        requester=requester,
        target=target,
        message=(message or "").strip()[:500],
    )
    notify_request_received(link)
    return link


def respond_to_request(link, actor, accept):
    """Answer a request as its target; approval creates the link.

    Ownership (``Application.agent``) is what "My Students", "New
    Application" and the chat framework all read, so approval writes that
    row — and opens the chat thread between the pair, exactly as adding a
    student directly does.
    """
    if link.target_id != actor.pk:
        raise PermissionError("Only the target may answer this request")
    if link.status != AgentLinkRequest.Status.PENDING:
        raise ValidationError(_("This request has already been answered."))

    conversation = None
    with transaction.atomic():
        link.status = (
            AgentLinkRequest.Status.APPROVED
            if accept
            else AgentLinkRequest.Status.DECLINED
        )
        link.responded_at = timezone.now()
        link.save()

        if accept:
            Application.objects.get_or_create(
                agent_id=link.requester_id, student_id=link.target_id
            )
            from core import chat as chat_domain

            conversation = chat_domain.get_or_create_conversation(
                link.requester, link.target
            )

    # After commit: a socket must never announce a link whose rows are not
    # visible yet (same ordering as submit_add_student).
    if conversation is not None:
        for user_id in (link.requester_id, link.target_id):
            push_to_user(user_id, {"type": "chat.refresh", "conversation": conversation.pk})

    notify_request_answered(link, accepted=accept)
    # The answerer's own count dropped the moment they answered; their open
    # tab learns it from the same badge event the requester gets.
    push_requests_badge(link.target)
    return link


def cancel_request(link, actor):
    """Withdraw a request the actor sent, while it is still pending."""
    if link.requester_id != actor.pk:
        raise PermissionError("Only the requester may cancel this request")
    if link.status != AgentLinkRequest.Status.PENDING:
        raise ValidationError(_("This request has already been answered."))
    link.status = AgentLinkRequest.Status.CANCELLED
    link.responded_at = timezone.now()
    link.save()
    # One fewer request waiting for the target's answer: move their badge too,
    # so a withdrawn request cannot sit in an open tab as still-pending.
    push_requests_badge(link.target)
    return link


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def received_requests(user):
    """Requests addressed to ``user`` — the ones awaiting their answer first."""
    return (
        AgentLinkRequest.objects.filter(target=user)
        .select_related("requester", "target")
        .order_by("-created_at")
    )


def sent_requests(user):
    """Requests ``user`` sent, newest first."""
    return (
        AgentLinkRequest.objects.filter(requester=user)
        .select_related("requester", "target")
        .order_by("-created_at")
    )


def pending_received_count(user):
    """How many requests are waiting for ``user``'s answer (sidebar badge)."""
    return AgentLinkRequest.objects.filter(
        target=user, status=AgentLinkRequest.Status.PENDING
    ).count()


def push_requests_badge(user):
    """Move the requests badge in the target's open tabs.

    The notification pipeline already moves the bell badge; this is the
    separate count of requests still awaiting an answer.
    """
    notify_user(
        user.pk,
        {"pending": pending_received_count(user)},
        type="requests.refresh",
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def requester_label(user):
    """How a requester is named in notifications and lists."""
    return user.get_full_name() or user.username


def notify_request_received(link):
    """Tell the target a representation request is waiting for them."""
    from core.utils.notifications import send_notification

    send_notification(
        user=link.target,
        title=_("New representation request"),
        message=_(
            "%(name)s asks to represent you as your agent. Open Requests to accept or decline."
        )
        % {"name": requester_label(link.requester)},
        notification_type="info",
        sender=link.requester,
        action_url=REQUESTS_PAGE,
    )
    push_requests_badge(link.target)


def notify_request_answered(link, accepted):
    """Tell the requester how their request was answered."""
    from core.utils.notifications import send_notification

    name = requester_label(link.target)
    if accepted:
        title = _("Representation request accepted")
        message = _(
            "%(name)s accepted your request. They are now one of your students and you can message them."
        ) % {"name": name}
        notification_type = "success"
    else:
        title = _("Representation request declined")
        message = _("%(name)s declined your representation request.") % {"name": name}
        notification_type = "warning"

    send_notification(
        user=link.requester,
        title=title,
        message=message,
        notification_type=notification_type,
        sender=link.target,
        action_url=REQUESTS_PAGE,
    )
    push_requests_badge(link.requester)


__all__ = [
    "PUBLIC_ID_LENGTH",
    "REQUESTS_PAGE",
    "normalize_public_id",
    "find_user_by_public_id",
    "is_managed_by",
    "pending_request_between",
    "can_send_request",
    "reason_message",
    "send_link_request",
    "respond_to_request",
    "cancel_request",
    "received_requests",
    "sent_requests",
    "pending_received_count",
    "push_requests_badge",
    "notify_request_received",
    "notify_request_answered",
]
