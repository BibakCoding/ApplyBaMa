"""Chat domain logic for ApplyBaMa.

The messaging framework is deliberately closed:

* the site admin (staff) is reachable by everyone;
* agents and companies reach the students they manage — ownership is read the
  same way "My Students" reads it, off the ``Application.agent`` link via
  :func:`dashboard.views.get_managed_students`;
* a student reaches their agent/company plus the admin;
* nothing else. There is no directory, no search over users and no way to
  message anyone outside these pairs, so the surface attackers care about
  (user enumeration, mass messaging, privilege escalation) does not exist.

Chat models (Conversation, ConversationParticipant, Message,
MessageAttachment, FilePermission) live in ``core.models`` with the rest of
the domain; this module holds pairing, authorization and upload policy.

Upload policy: without an active ``FilePermission`` row a student cannot
attach files at all. With one, the per-file allowance is the granted
``max_file_mb`` (the grant dialog pre-fills ``SiteSettings.chat_default_file_mb``
and may raise or lower it), bounded by ``CHAT_FILE_MAX_MB``. The site-wide
total is bounded by ``SiteSettings.chat_max_total_storage_mb``.
"""

import os

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from core.models import (
    AgentProfile,
    Application,
    CompanyProfile,
    Conversation,
    ConversationParticipant,
    FilePermission,
    Message,
    MessageAttachment,
    User,
)

# Hard ceiling for any per-student allowance: a grant may raise a student's
# limit above the site default, but never above this, and it also bounds what
# a forged POST can try to allocate.
CHAT_FILE_MAX_MB = 50

# Accepted upload types. Images get inline previews; everything else renders
# as a download chip. The list is intentionally short — executables and
# archives are the classic malware vector in a contact surface.
CHAT_FILE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"]

_chat_file_validator = FileExtensionValidator(
    allowed_extensions=[ext.lstrip(".") for ext in CHAT_FILE_EXTENSIONS]
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ---------------------------------------------------------------------------
# Partner resolution — the entire permission model lives here and in
# user_can_message(); every other function defers to those two.
# ---------------------------------------------------------------------------


def managing_accounts_for(student):
    """The accounts that manage ``student`` — the mirror of the ownership link.

    ``get_managed_students()`` reads ownership top-down (agent/company → the
    students they hold); a student needs the same link read bottom-up to reach
    their agent/company, so this walks the student's applications: each
    application's ``agent`` is the acting account, and an agent's company is
    reached through its ``AgentProfile.agency``. Both directions therefore
    describe exactly the same pairs.
    """
    agent_ids = set(
        Application.objects.filter(student=student).values_list("agent_id", flat=True)
    )
    if not agent_ids:
        return set()
    company_ids = set(
        AgentProfile.objects.filter(user_id__in=agent_ids).values_list(
            "agency__user_id", flat=True
        )
    )
    return agent_ids | company_ids


def chat_partners_for(user):
    """The users ``user`` may open a conversation with.

    Returns a list of ``(User, label)`` tuples, with the admin conversation
    first — it is the one everyone shares. The list is what the chat page
    offers as "start a conversation"; it never grows beyond the framework's
    pairs, so it is not a user directory.
    """
    partners = []

    if not user.is_staff:
        admins = (
            User.objects.filter(is_staff=True, is_active=True)
            .exclude(pk=user.pk)
            .order_by("id")
        )
        for admin in admins:
            partners.append((admin, _("Support")))

    if user.user_type == User.UserType.DEFAULT:
        for account in User.objects.filter(
            pk__in=managing_accounts_for(user), is_active=True
        ).order_by("id"):
            label = _("Agent")
            if account.user_type == User.UserType.COMPANY:
                profile = CompanyProfile.objects.filter(user=account).first()
                label = profile.company_name if profile else _("Company")
            partners.append((account, label))

    elif user.user_type in (User.UserType.AGENT, User.UserType.COMPANY):
        from dashboard.views import get_managed_students

        for student_id in get_managed_students(user):
            student = User.objects.filter(pk=student_id, is_active=True).first()
            if student is None:
                continue
            partners.append((student, _("Student")))

    return partners


def user_can_message(sender, recipient):
    """True when ``sender`` may open/continue a chat with ``recipient``.

    Single source of truth for authorization; views and the WebSocket consumer
    both defer here. The relation is symmetric by construction — both
    directions read the same ownership link (``get_managed_students`` going
    down, :func:`managing_accounts_for` coming back up) — so if a can see b,
    b can see a.
    """
    from dashboard.views import get_managed_students

    if not sender or not recipient:
        return False
    if not (sender.is_authenticated and recipient.is_active):
        return False
    if sender.pk == recipient.pk:
        return False

    # Staff ↔ user is always allowed: the admin is open to everyone.
    if sender.is_staff or recipient.is_staff:
        return True

    # The agent/company side asks "is this one of my students?" — the same
    # list "My Students" renders.
    if recipient.user_type == User.UserType.DEFAULT:
        return recipient.pk in set(get_managed_students(sender))
    # The student side asks the mirror question: "does this account manage me?"
    if sender.user_type == User.UserType.DEFAULT:
        return recipient.pk in managing_accounts_for(sender)
    # No agent↔agent, company↔company, agent↔company traffic: the framework
    # defines admin↔everyone and agent/company↔their-students, nothing else.
    return False


def get_or_create_conversation(user_a, user_b):
    """Return the single conversation for the pair, creating it if needed.

    Callers must have authorized the pair (partner list or user_can_message);
    the ordered-pair unique constraint guarantees one row per pair even under
    concurrent first contact.
    """
    low, high = sorted((user_a, user_b), key=lambda u: u.pk)
    conversation, _created = Conversation.objects.get_or_create(
        user_low=low, user_high=high
    )
    return conversation


def conversations_for(user):
    """All of ``user``'s conversations, newest activity first."""
    return (
        Conversation.objects.filter(Q(user_low=user) | Q(user_high=user))
        .select_related("user_low", "user_high")
        .order_by("-last_message_at", "-id")
    )


def participant_reads(conversation):
    """``{user_id: last_read_at}`` for both participants in one query."""
    return {
        row["user_id"]: row["last_read_at"]
        for row in ConversationParticipant.objects.filter(conversation=conversation)
        .values("user_id", "last_read_at")
    }


def unread_counts_for(user):
    """Unread message counts per conversation for the sidebar badge.

    A message is unread when it is visible (not soft-deleted), sent by the
    peer, and newer than the reader's ``last_read_at`` marker (a missing
    marker means nothing has been read yet).
    """
    counts = {}
    for conversation in conversations_for(user):
        peer = conversation.partner_of(user)
        reads = participant_reads(conversation)
        last_read = reads.get(user.pk)
        qs = conversation.messages.filter(is_deleted=False, sender=peer)
        if last_read:
            qs = qs.filter(created_at__gt=last_read)
        count = qs.count()
        if count:
            counts[conversation.pk] = count
    return counts


def total_unread_for(user):
    """Sum of :func:`unread_counts_for` — the sidebar badge number."""
    return sum(unread_counts_for(user).values())


def mark_conversation_read(conversation, user):
    """Advance ``user``'s read marker; returns the previous marker (or None).

    The double-check logic on the peer's client compares message timestamps
    against this marker, so it is set on the reader's own participation row.
    """
    marker, _created = ConversationParticipant.objects.get_or_create(
        conversation=conversation, user=user
    )
    previous = marker.last_read_at
    now = timezone.now()
    if previous is None or previous < now:
        marker.last_read_at = now
        marker.save(update_fields=["last_read_at"])
    return previous


def set_presence(user, online):
    """Flip ``is_online`` on every conversation the user takes part in.

    Called by the consumer on socket connect/disconnect. Two queries, both
    narrow: presence only matters to the user's chat partners.
    """
    ConversationParticipant.objects.filter(
        conversation__in=conversations_for(user), user=user
    ).update(is_online=online)


def peers_of(user):
    """Distinct users sharing a conversation with ``user`` (presence pushes)."""
    ids = set()
    for conversation in conversations_for(user):
        ids.add(conversation.partner_of(user).pk)
    return ids


# ---------------------------------------------------------------------------
# Message surface
# ---------------------------------------------------------------------------


def messages_for(conversation):
    """The visible message surface of a conversation, oldest first."""
    return (
        conversation.messages.select_related("sender", "reply_to", "forwarded_from")
        .prefetch_related("attachments")
        .order_by("created_at")
    )


def serialize_message(message, viewer_id, reads=None):
    """JSON shape pushed to the browser and rendered by chat.js.

    ``reads`` is the participant-read map when the caller has it (avoids a
    query per message); deleted messages collapse to their placeholder shape.
    """
    if reads is None:
        reads = participant_reads(message.conversation)

    data = {
        "id": message.pk,
        "conversation": message.conversation_id,
        "sender": message.sender_id,
        "mine": message.sender_id == viewer_id,
        "created_at": message.created_at.isoformat(),
        "is_deleted": message.is_deleted,
        "is_edited": message.is_edited,
        "is_pinned": message.is_pinned,
        "reply_to": message.reply_to_id,
        "forwarded_from": message.forwarded_from_id,
        "attachments": [],
    }
    if message.is_deleted:
        # Soft-deleted: hidden content, the row (and file) stay in the DB.
        data["body"] = ""
        data["deleted"] = True
        return data

    data["body"] = message.body
    if message.reply_to_id:
        parent = message.reply_to
        if parent.is_deleted:
            data["reply_preview"] = {"deleted": True}
        else:
            data["reply_preview"] = {
                "sender": parent.sender_id,
                "body": (parent.body or "")[:120],
                "has_file": parent.has_file,
            }
    data["forwarded"] = message.forwarded_from_id is not None

    # Double check for MY messages: has the PEER read past this message?
    peer_id = (
        message.conversation.user_high_id
        if message.conversation.user_low_id == message.sender_id
        else message.conversation.user_low_id
    )
    peer_read = reads.get(peer_id)
    data["read"] = bool(
        peer_read and message.created_at and peer_read >= message.created_at
    )

    for attachment in message.attachments.all():
        data["attachments"].append(
            {
                "id": attachment.pk,
                "name": attachment.original_name,
                "size": attachment.size,
                "is_image": attachment.is_image,
                "url": attachment.file.url,
            }
        )
    return data


def send_message(conversation, sender, body="", reply_to=None, forwarded_from=None):
    """Create a message inside an authorized conversation and bump the thread.

    Returns the message. Attachments are added by the upload endpoint before
    the realtime push happens (upload → attach → push), so a message never
    announces itself with missing files.
    """
    if not conversation.is_participant(sender):
        raise PermissionError("Not a participant of this conversation")
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=(body or "").strip(),
        reply_to=reply_to,
        forwarded_from=forwarded_from,
    )
    conversation.touch()
    # Sending implicitly reads the thread up to now: the sender has plainly
    # seen everything above their own message.
    mark_conversation_read(conversation, sender)
    return message


def forward_message(message, target_conversation, sender):
    """Copy ``message`` into ``target_conversation`` with the Forwarded label.

    Body and attachments are duplicated (the original stays where it is);
    file copies share storage via a new upload only when re-sent — here the
    attachment rows point at the same underlying files, which keeps forwarding
    cheap. Only the body+file reference is duplicated, never the origin row.
    """
    if not target_conversation.is_participant(sender):
        raise PermissionError("Not a participant of the target conversation")
    if message.is_deleted:
        raise ValidationError(_("That message was deleted."))
    copy = Message.objects.create(
        conversation=target_conversation,
        sender=sender,
        body=message.body,
        forwarded_from=message,
    )
    for attachment in message.attachments.all():
        MessageAttachment.objects.create(
            message=copy,
            file=attachment.file,
            original_name=attachment.original_name,
            size=attachment.size,
            content_type=attachment.content_type,
            is_image=attachment.is_image,
        )
    target_conversation.touch()
    mark_conversation_read(target_conversation, sender)
    return copy


# ---------------------------------------------------------------------------
# Upload policy
# ---------------------------------------------------------------------------


def user_file_allowance_mb(user):
    """MB allowed per upload for ``user``, or None when uploads are closed."""
    if user.is_staff:
        # The admin grants files to others; their own uploads are bounded by
        # the ceiling only.
        return CHAT_FILE_MAX_MB
    return FilePermission.allowance_mb_for(user)


def validate_chat_upload(upload_file, user):
    """Raise ValidationError when ``upload_file`` may not be sent by ``user``.

    Extension, per-file size and the site-wide storage ceiling are all checked
    here, before anything touches the disk.
    """
    _chat_file_validator(upload_file)

    allowance = user_file_allowance_mb(user)
    if allowance is None:
        raise ValidationError(_("You do not have permission to send files in chat."))

    size_mb = upload_file.size / (1024 * 1024)
    if size_mb > allowance:
        raise ValidationError(
            _("This file is too large. Your limit is %(limit)s MB.")
            % {"limit": allowance}
        )

    from core.models import SiteSettings

    site = SiteSettings.objects.get_or_create(pk=1)[0]
    used_mb = (MessageAttachment.objects.aggregate(total=Sum("size"))["total"] or 0) / (
        1024 * 1024
    )
    if used_mb + size_mb > site.chat_max_total_storage_mb:
        raise ValidationError(
            _("The site's chat storage is full. Please try again later.")
        )


def is_image_file(name):
    _, ext = os.path.splitext(name)
    return ext.lower() in IMAGE_EXTENSIONS
