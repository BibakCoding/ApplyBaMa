"""Chat HTTP endpoints.

The SPA opens ``chat`` as a normal fragment (dashboard_content), which renders
the conversation list; the thread, the composer and every action below are
JSON calls from ``static/js/pages/chat.js``.

Two authorization gates run on every object access:

* :func:`core.chat.user_can_message` for starting conversations;
* ``conversation.is_participant`` for touching an existing one.

Mass messaging is structurally impossible — there is no endpoint that accepts
more than one recipient — and ``django_ratelimit`` bounds the endpoints that
write rows (send, forward, upload) the way it already bounds registration and
email sending in this project.
"""

import json

from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from core import chat as chat_domain
from core.models import Conversation, ConversationParticipant, FilePermission, Message, MessageAttachment, User
from dashboard.views import email_verification_required, login_required
from realtime.push import push_to_user


def _denied(message=None):
    return JsonResponse(
        {"success": False, "message": message or _("You cannot message this user.")},
        status=403,
    )


def _message_payload(message, viewer_id):
    """Serialize one message plus the conversation-level read markers."""
    return chat_domain.serialize_message(
        message, viewer_id, reads=chat_domain.participant_reads(message.conversation)
    )


def _push_message(message, unread_total):
    """Announce a newly created message to both participants."""
    payload = dict(_message_payload(message, message.sender_id))
    payload["type"] = "chat.message"
    payload["unread_total"] = unread_total
    for participant in message.conversation.both_users():
        push_to_user(participant.pk, payload)


def _push_state(conversation, event_type, extra=None):
    """Push a conversation-state event (edit/delete/pin/read) to both sides."""
    base = {"type": event_type, "conversation": conversation.pk}
    if extra:
        base.update(extra)
    for participant in conversation.both_users():
        push_to_user(participant.pk, base)


# ---------------------------------------------------------------------------
# Fragment + page data
# ---------------------------------------------------------------------------


def _conversation_summary(conversation, user, reads=None):
    peer = conversation.partner_of(user)
    reads = reads if reads is not None else chat_domain.participant_reads(conversation)
    last = (
        conversation.messages.select_related("sender")
        .prefetch_related("attachments")
        .order_by("-created_at")
        .first()
    )
    unread = 0
    last_read = reads.get(user.pk)
    if last and last.sender_id != user.pk:
        unread_qs = conversation.messages.filter(is_deleted=False, sender=peer)
        if last_read:
            unread_qs = unread_qs.filter(created_at__gt=last_read)
        unread = unread_qs.count()
    return {
        "id": conversation.pk,
        "peer": {
            "id": peer.pk,
            "name": peer.get_full_name() or peer.username,
            "username": peer.username,
            "is_staff": peer.is_staff,
            "online": _peer_online(conversation, peer),
        },
        "last_message": _summary_line(last),
        "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        "unread": unread,
    }


def _summary_line(last):
    if last is None:
        return ""
    if last.is_deleted:
        return _("Message deleted")
    if last.body:
        return last.body[:80]
    if last.has_file:
        return _("📎 Attachment")
    return ""


def _peer_online(conversation, peer):
    return ConversationParticipant.objects.filter(
        conversation=conversation, user=peer, is_online=True
    ).exists()


def _thread_data(conversation, user):
    reads = chat_domain.participant_reads(conversation)
    peer = conversation.partner_of(user)
    messages = [
        chat_domain.serialize_message(m, user.pk, reads=reads)
        for m in chat_domain.messages_for(conversation)
    ]
    my_read = reads.get(user.pk)
    return {
        "id": conversation.pk,
        "peer": {
            "id": peer.pk,
            "name": peer.get_full_name() or peer.username,
            "username": peer.username,
            "is_staff": peer.is_staff,
            "online": _peer_online(conversation, peer),
        },
        "messages": messages,
        "pinned": _pinned_payload(conversation),
        "my_last_read_at": my_read.isoformat() if my_read else None,
        # When the peer last opened this thread: the read time shown next to
        # the double check on my own messages.
        "peer_last_read_at": (
            reads.get(peer.pk).isoformat() if reads.get(peer.pk) else None
        ),
        "can_file": chat_domain.user_file_allowance_mb(user),
        "file_ceiling": chat_domain.CHAT_FILE_MAX_MB,
    }


def _pinned_payload(conversation):
    pinned = conversation.messages.filter(is_pinned=True, is_deleted=False).first()
    if pinned is None:
        return None
    return {"id": pinned.pk, "body": (pinned.body or "")[:140]}


@login_required
def conversations_data(request):
    """JSON for the conversation list (chat.js re-fetches on chat.* events).

    Alongside the open threads it publishes the *contacts* the framework
    allows but that have no thread yet (the admin for everyone, the students an
    agent/company manages, the managing accounts for a student). That is how a
    first message is started without a user directory: the list is computed
    from the ownership link, never from a search box.
    """
    conversations = list(chat_domain.conversations_for(request.user))
    items = [_conversation_summary(c, request.user) for c in conversations]
    existing = {c.partner_of(request.user).pk for c in conversations}
    contacts = [
        {
            "id": partner.pk,
            "name": partner.get_full_name() or partner.username,
            "label": label,
            "is_staff": partner.is_staff,
        }
        for partner, label in chat_domain.chat_partners_for(request.user)
        if partner.pk not in existing
    ]
    return JsonResponse(
        {
            "success": True,
            "conversations": items,
            "contacts": contacts,
            # The viewer's own upload allowance, so a thread opened from a
            # contact row can render the composer before any message exists.
            "can_file": chat_domain.user_file_allowance_mb(request.user),
        }
    )


@login_required
def thread_data(request, pk):
    """JSON for the open thread (poll-free: initial load + event diffs)."""
    conversation = Conversation.objects.filter(pk=pk).first()
    if conversation is None or not conversation.is_participant(request.user):
        return _denied()
    return JsonResponse({"success": True, "thread": _thread_data(conversation, request.user)})


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


@login_required
@require_POST
@email_verification_required
@ratelimit(key="user", rate="30/m", method="POST", block=True)
def send_message(request):
    """Create a message (text) or attach files to a pending one.

    Body is the only free-form field; reply/forward references are validated
    to live inside the same conversation. One recipient per request: there is
    no broadcast endpoint.
    """
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)

    partner_id = payload.get("partner")
    body = (payload.get("body") or "").strip()
    if not partner_id or not body:
        return JsonResponse(
            {"success": False, "message": _("Message cannot be empty.")}, status=400
        )
    if len(body) > 4000:
        return JsonResponse(
            {"success": False, "message": _("Message is too long (max 4000 characters).")},
            status=400,
        )

    partner = User.objects.filter(pk=partner_id, is_active=True).first()
    if partner is None or not chat_domain.user_can_message(request.user, partner):
        return _denied()

    conversation = chat_domain.get_or_create_conversation(request.user, partner)

    reply_to = None
    if payload.get("reply_to"):
        reply_to = conversation.messages.filter(
            pk=payload["reply_to"], is_deleted=False
        ).first()
    forwarded_from = None
    if payload.get("forwarded_from"):
        origin = Message.objects.filter(pk=payload["forwarded_from"]).first()
        if (
            origin
            and not origin.is_deleted
            and origin.conversation.is_participant(request.user)
        ):
            forwarded_from = origin
        else:
            return _denied()

    message = chat_domain.send_message(
        conversation,
        request.user,
        body=body,
        reply_to=reply_to,
        forwarded_from=forwarded_from,
    )
    _push_message(message, chat_domain.total_unread_for(partner))
    return JsonResponse(
        {"success": True, "message": _message_payload(message, request.user.pk)}
    )


@login_required
@require_POST
@email_verification_required
@ratelimit(key="user", rate="10/m", method="POST", block=True)
def upload_attachment(request, pk):
    """Attach one already-created message's file.

    The flow is: send_message (creates the text/empty message) → one upload
    call per file → chat.js pushes nothing (send already did). Files are
    validated, size-capped and quota-checked BEFORE storage is touched.
    """
    conversation = Conversation.objects.filter(pk=pk).first()
    if conversation is None or not conversation.is_participant(request.user):
        return _denied()

    message = conversation.messages.filter(
        sender=request.user, is_deleted=False
    ).order_by("-created_at").first()
    if message is None:
        return JsonResponse(
            {"success": False, "message": _("Send a message first.")}, status=400
        )

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse(
            {"success": False, "message": _("No file received.")}, status=400
        )

    try:
        chat_domain.validate_chat_upload(uploaded, request.user)
    except Exception as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)

    attachment = MessageAttachment.objects.create(
        message=message,
        file=uploaded,
        original_name=uploaded.name[:255],
        size=uploaded.size,
        content_type=uploaded.content_type or "",
        is_image=chat_domain.is_image_file(uploaded.name),
    )
    _push_state(
        conversation,
        "chat.message.update",
        {"message": _message_payload(message, request.user.pk)},
    )
    return JsonResponse(
        {
            "success": True,
            "attachment": {
                "id": attachment.pk,
                "name": attachment.original_name,
                "size": attachment.size,
                "is_image": attachment.is_image,
                "url": attachment.file.url,
            },
        }
    )


# ---------------------------------------------------------------------------
# Message actions
# ---------------------------------------------------------------------------


def _own_message(request, message_id):
    message = Message.objects.filter(pk=message_id).first()
    if message is None or not message.conversation.is_participant(request.user):
        return None
    return message


@login_required
@require_POST
@email_verification_required
def edit_message(request, pk):
    """Edit own message text (the UI shows an \"edited\" mark afterwards)."""
    message = _own_message(request, pk)
    if message is None:
        return _denied()
    if message.sender_id != request.user.pk:
        return _denied(_("You can only edit your own messages."))

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)

    body = (payload.get("body") or "").strip()
    if not body or len(body) > 4000:
        return JsonResponse(
            {"success": False, "message": _("Message cannot be empty.")}, status=400
        )

    message.body = body
    message.is_edited = True
    message.save(update_fields=["body", "is_edited", "updated_at"])
    _push_state(message.conversation, "chat.message.update", {"message": _message_payload(message, request.user.pk)})
    return JsonResponse({"success": True, "message": _message_payload(message, request.user.pk)})


@login_required
@require_POST
@email_verification_required
def delete_message(request, pk):
    """Soft-delete own message: hidden for both, the row stays in the DB."""
    message = _own_message(request, pk)
    if message is None:
        return _denied()
    if message.sender_id != request.user.pk:
        return _denied(_("You can only delete your own messages."))

    message.soft_delete(request.user)
    _push_state(message.conversation, "chat.message.update", {"message": _message_payload(message, request.user.pk)})
    return JsonResponse({"success": True})


@login_required
@require_POST
@email_verification_required
def pin_message(request, pk):
    """Pin own message (one pinned per conversation, Telegram-style)."""
    message = _own_message(request, pk)
    if message is None:
        return _denied()
    if message.sender_id != request.user.pk:
        return _denied(_("You can only pin your own messages."))

    if message.is_pinned:
        message.is_pinned = False
        message.save(update_fields=["is_pinned", "updated_at"])
    else:
        message.conversation.messages.filter(is_pinned=True).update(is_pinned=False)
        message.is_pinned = True
        message.save(update_fields=["is_pinned", "updated_at"])

    _push_state(
        message.conversation,
        "chat.pinned",
        {"pinned": _pinned_payload(message.conversation)},
    )
    return JsonResponse({"success": True, "pinned": _pinned_payload(message.conversation)})


@login_required
@require_POST
@email_verification_required
def read_thread(request, pk):
    """Mark the thread read (sent by chat.js when the thread is open)."""
    conversation = Conversation.objects.filter(pk=pk).first()
    if conversation is None or not conversation.is_participant(request.user):
        return _denied()
    chat_domain.mark_conversation_read(conversation, request.user)
    unread_total = chat_domain.total_unread_for(request.user)
    _push_state(
        conversation,
        "chat.read",
        {
            "reader": request.user.pk,
            "last_read_at": timezone.now().isoformat(),
            "unread_total": unread_total,
        },
    )
    return JsonResponse({"success": True, "unread_total": unread_total})


@login_required
@require_POST
@email_verification_required
@ratelimit(key="user", rate="20/m", method="POST", block=True)
def forward_message(request, pk):
    """Copy a visible message into one of the sender's other conversations."""
    origin = _own_message(request, pk)
    if origin is None or origin.is_deleted:
        return _denied()

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)

    partner_id = payload.get("partner")
    partner = User.objects.filter(pk=partner_id, is_active=True).first()
    if partner is None or not chat_domain.user_can_message(request.user, partner):
        return _denied()

    target = chat_domain.get_or_create_conversation(request.user, partner)
    if target.pk == origin.conversation_id:
        return JsonResponse(
            {"success": False, "message": _("Pick a different conversation.")}, status=400
        )

    copy = chat_domain.forward_message(origin, target, request.user)
    _push_message(copy, chat_domain.total_unread_for(partner))
    return JsonResponse({"success": True})


# ---------------------------------------------------------------------------
# File-permission grants (admin, agent, company)
# ---------------------------------------------------------------------------


def _grantable_student(request, student_id):
    """The student this account may grant file rights to, or None.

    Staff may grant to any student. Agents/companies may grant to the students
    they manage (the same ownership link the chat permission model uses).
    """
    student = User.objects.filter(pk=student_id, user_type=User.UserType.DEFAULT).first()
    if student is None:
        return None
    if request.user.is_staff:
        return student
    from dashboard.views import get_managed_students

    if student.pk in set(get_managed_students(request.user)):
        return student
    return None


@login_required
@require_POST
@email_verification_required
def grant_file_permission(request, student_id):
    """Grant (or revoke) a student's chat file allowance.

    ``max_file_mb`` is optional: omitted means the site default from Site
    Settings. The value is clamped to 1..CHAT_FILE_MAX_MB so no forged POST can
    widen it. ``revoke`` deactivates the row (uploads stop immediately).
    """
    student = _grantable_student(request, student_id)
    if student is None:
        return _denied(_("You can only manage your own students."))

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": _("Invalid request.")}, status=400)

    if payload.get("revoke"):
        FilePermission.objects.filter(student=student).update(is_active=False)
        _push_state_chat_file(student, None)
        return JsonResponse({"success": True, "granted": False})

    row, _created = FilePermission.grant(
        student,
        granted_by=request.user,
        max_file_mb=payload.get("max_file_mb"),
    )
    _push_state_chat_file(student, row.max_file_mb)
    return JsonResponse({"success": True, "granted": True, "max_file_mb": row.max_file_mb})


def _push_state_chat_file(student, max_file_mb):
    """Tell the student's open tabs their new upload allowance."""
    push_to_user(
        student.pk,
        {"type": "chat.file.permission", "max_file_mb": max_file_mb},
    )
