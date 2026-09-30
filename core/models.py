# core/models.py
import os

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import JSONField
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .utils.image_processing import university_logo_upload_to, compress_image
from django.conf import settings


# -----------------------------------------------------------------------------
# TimestampedModel (abstract base for created/updated timestamps)
# -----------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# -----------------------------------------------------------------------------
# File validation functions
# -----------------------------------------------------------------------------
def validate_image_file_extension(value):
    valid_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(
            _("Unsupported file extension. Allowed: .jpg, .jpeg, .png, .gif, .webp")
        )


def validate_document_file_extension(value):
    valid_extensions = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(
            _(
                "Unsupported file extension. Allowed: .pdf, .doc, .docx, .jpg, .jpeg, .png"
            )
        )


# -----------------------------------------------------------------------------
# File path generators
# -----------------------------------------------------------------------------
def user_profile_image_path(instance, filename):
    """Generate path for user profile images"""
    random_name = get_random_string(length=16)
    ext = os.path.splitext(filename)[1]
    return f"profile_images/{instance.username}/{random_name}{ext}"


def application_document_upload_to(instance, filename):
    """Generate path for application documents"""
    random_name = get_random_string(length=16)
    ext = os.path.splitext(filename)[1]
    return f"application_documents/{instance.application_name}/{random_name}{ext}"


# -----------------------------------------------------------------------------
# Lookup tables
# -----------------------------------------------------------------------------
class Country(TimeStampedModel):
    external_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text=_("ID from info.studyfans.com"),
    )
    name = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(
        max_length=100, help_text=_("Primary language"), blank=True, null=True
    )
    nationality = models.CharField(
        max_length=100, help_text=_("Nationality adjective"), blank=True, null=True
    )

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="country_name_ci_unique")
        ]

    def __str__(self):
        return self.name or ""


# ---------------------------------------------------------------------------
# City (now with external_id)
# ---------------------------------------------------------------------------
class City(TimeStampedModel):
    external_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text=_("ID from info.studyfans.com"),
    )
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="cities"
    )
    name = models.CharField(max_length=100)

    class Meta:
        # Singular and plural are both declared: Django appends an "s" to derive
        # the plural ("citys", "facultys", "universitys") and the admin shows the
        # lowercase model name where no singular is set — untranslated, which put
        # English model names inside Persian/Turkish/Arabic admin headings.
        verbose_name = _("City")
        verbose_name_plural = _("Cities")
        unique_together = ("country", "name")

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class TermOption(TimeStampedModel):
    label = models.CharField(max_length=50)

    class Meta:
        verbose_name = _("Term Option")
        verbose_name_plural = _("Term Options")

    def __str__(self):
        return self.label


class YearOption(TimeStampedModel):
    VALUE_CHOICES = [
        ("1", "1"),
        ("1.5", "1.5"),
        ("2", "2"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6"),
    ]
    value = models.CharField(
        max_length=10,
        choices=VALUE_CHOICES,
        unique=True,
        help_text=_("Number of years—for example, '1', '1.5', '2', etc."),
    )

    class Meta:
        verbose_name = _("Year Option")
        verbose_name_plural = _("Year Options")

    def __str__(self):
        return self.get_value_display()


class Faculty(TimeStampedModel):
    name = models.CharField(max_length=200)
    year_options = models.ManyToManyField(
        YearOption,
        blank=True,
        related_name="faculties",
        help_text=_(
            "Select one or more possible durations (in years) that this faculty offers."
        ),
    )

    class Meta:
        verbose_name = _("Faculty")
        verbose_name_plural = _("Faculties")

    def __str__(self):
        return self.name


class University(TimeStampedModel):
    SECTOR_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
        ("other", "Other"),
    ]

    logo = models.ImageField(upload_to=university_logo_upload_to, blank=True, null=True)

    show_on_homepage = models.BooleanField(
        default=False, help_text="Display in the trust banner?"
    )

    external_id = models.IntegerField(
        unique=True, null=True, blank=True, help_text=_("ID from info.studyfans.com")
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide from public site while preserving applications.",
    )

    name = models.CharField(max_length=255, unique=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="universities",
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="universities",
    )
    address = models.CharField(max_length=500, blank=True)
    website = models.URLField(blank=True, null=True)

    parsed_data = JSONField(
        default=dict,
        blank=True,
        help_text=_(
            "Parsed details (dates, exams, documents, fees, etc.) from the site"
        ),
    )

    sector = models.CharField(max_length=20, choices=SECTOR_CHOICES, default="private")
    founded_in = models.PositiveIntegerField(
        blank=True, null=True, help_text=_("Year founded, e.g. 2013")
    )
    main_campus = models.CharField(max_length=255, blank=True)
    pin_code = models.CharField(
        max_length=20, blank=True, null=True, help_text=_("University PIN code")
    )
    faculties = models.ManyToManyField(Faculty, blank=True, related_name="universities")
    available_languages = models.ManyToManyField(
        Country,
        blank=True,
        related_name="language_universities",
        help_text=_("Which country languages are taught/used by this university"),
    )

    class Meta:
        verbose_name = _("University")
        verbose_name_plural = _("Universities")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="university_name_ci_unique")
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Compress image only if it's newly uploaded or changed
        if self.logo and hasattr(self.logo, "file"):
            if not self.pk or University.objects.get(pk=self.pk).logo != self.logo:
                compress_image(self.logo)
        super().save(*args, **kwargs)

    @property
    def programs_count(self):
        return self.programs.count()

    @property
    def starting_fee(self):
        # Get the minimum valid display price across all programs
        prices = [p.display_price for p in self.programs.all() if p.display_price > 0]
        return min(prices) if prices else 0

    @property
    def available_languages(self):
        # Return a unique list of languages offered by the university's programs
        return list(set(p.language for p in self.programs.all() if p.language))


class Program(TimeStampedModel):
    class Meta:
        verbose_name = _("Program")
        verbose_name_plural = _("Programs")

    class StatusChoices(models.TextChoices):
        AVAILABLE = "available", _("Available")
        NEAR_TO_CLOSE = "near_to_close", _("Near to Close")
        QUOTA_FULL = "quota_full", _("Quota Full")
        CLOSED = "closed", _("Closed")

    DEGREE_CHOICES = [
        ("associate", "Associate"),
        ("bachelor", "Bachelor"),
        ("master", "Master"),
        ("phd", "PhD"),
        ("integrated_phd", "Integrated PhD"),
    ]

    external_id = models.IntegerField(
        unique=True, null=True, blank=True, help_text=_("ID from info.studyfans.com")
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide from public site while preserving applications.",
    )

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=15, choices=StatusChoices.choices, default=StatusChoices.AVAILABLE
    )
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="programs"
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programs",
    )
    degree = models.CharField(max_length=20, choices=DEGREE_CHOICES)
    duration = models.CharField(
        max_length=10,
        choices=YearOption.VALUE_CHOICES,
        blank=True,
        help_text=_("Duration in years; should be one of the faculty's year options"),
    )
    deposit_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prep_school_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    semester_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Fee per semester"),
    )
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    offer = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Scholarship or discount offered"),
    )
    term = models.ForeignKey(
        TermOption, on_delete=models.SET_NULL, null=True, blank=True
    )
    language = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Language of instruction, e.g. English, Turkish"),
    )
    currency = models.CharField(
        max_length=10, blank=True, help_text=_("Currency code, e.g. USD, EUR, TRY")
    )

    @property
    def original_price(self):
        # The main fee is usually prep_school_fee or cash_fees, but we check all to be safe
        fees = [
            self.prep_school_fee or 0,
            self.cash_fees or 0,
            self.deposit_fee or 0,
            self.semester_fee or 0,
        ]
        valid_fees = [f for f in fees if f > 0]
        return max(valid_fees) if valid_fees else 0

    @property
    def display_price(self):
        # If there is a valid offer (discount), use it as the display price
        if self.offer and self.offer > 0 and self.original_price > self.offer:
            return self.offer
        return self.original_price

    @property
    def is_discounted(self):
        return bool(self.offer and self.offer > 0 and self.original_price > self.offer)

    def __str__(self):
        return f"{self.name} @ {self.university.name}"


# -----------------------------------------------------------------------------
# Custom User + Profiles
# -----------------------------------------------------------------------------
class User(AbstractUser):
    class UserType(models.TextChoices):
        DEFAULT = "default", _("Default")
        COMPANY = "company", _("Company")
        AGENT = "agent", _("Agent")

    class GenderChoices(models.TextChoices):
        MALE = "male", _("Male")
        FEMALE = "female", _("Female")

    user_type = models.CharField(
        max_length=10, choices=UserType.choices, default=UserType.DEFAULT
    )
    gender = models.CharField(
        max_length=10, choices=GenderChoices.choices, blank=True, null=True
    )
    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="origin_users",
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="origin_city_users",
    )
    date_of_birth = models.DateField(blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    citizenship = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="citizens",
    )
    mobile = models.CharField(max_length=20, blank=True, null=True)
    profile_image = models.ImageField(
        upload_to=user_profile_image_path,
        null=True,
        blank=True,
        verbose_name=_("Profile Image"),
        help_text=_("Upload a profile image (max 2MB)"),
        validators=[validate_image_file_extension],
    )
    is_representative = models.BooleanField(
        default=False,
        help_text=_(
            "Designates whether this student can access representative features"
        ),
    )
    # Pending email change: the address the user wants to switch to. Empty
    # means no change is in progress. While a pending address exists the
    # dashboard treats the email as unverified (read-only mode).
    pending_email = models.EmailField(
        blank=True,
        null=True,
        help_text=_(
            "New email address awaiting verification; empty when no change is in progress"
        ),
    )
    # The current email address has been confirmed through a verification
    # link (or code, at registration). Unverified means read-only mode.
    email_verified = models.BooleanField(
        default=False,
        help_text=_("The current email address has been confirmed"),
    )

    @property
    def is_fully_verified(self):
        """True when the account may use every feature.

        A pending email change puts the account back into read-only mode
        until the new address is confirmed (or the request is cancelled),
        exactly like an address that was never verified.
        """
        return self.email_verified and not self.pending_email

    def __str__(self):
        return self.get_username()

    def clean(self):
        if self.is_representative and self.user_type != User.UserType.DEFAULT:
            raise ValidationError(_("Only student users can be representatives"))

    def save(self, *args, **kwargs):
        # Compress profile image only if it's newly uploaded or changed
        if self.profile_image and hasattr(self.profile_image, "file"):
            if (
                not self.pk
                or User.objects.get(pk=self.pk).profile_image != self.profile_image
            ):
                compress_image(self.profile_image, max_size=(500, 500), quality=85)
        super().save(*args, **kwargs)


class CompanyProfile(TimeStampedModel):
    class Meta:
        verbose_name = _("Company Profile")
        verbose_name_plural = _("Company Profiles")

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="company_profile"
    )
    company_name = models.CharField(max_length=255)
    company_email = models.EmailField()
    tax_number = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    website = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.company_name


class AgentProfile(TimeStampedModel):
    class Meta:
        verbose_name = _("Agent Profile")
        verbose_name_plural = _("Agent Profiles")

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="agent_profile"
    )
    agency = models.ForeignKey(
        CompanyProfile, on_delete=models.CASCADE, related_name="agents"
    )

    def __str__(self):
        return f"{self.user.get_full_name()} (Agent of {self.agency.company_name})"


class StudentProfile(TimeStampedModel):
    class Meta:
        verbose_name = _("Student Profile")
        verbose_name_plural = _("Student Profiles")

    STAGE_CHOICES = [
        ("freshman", "Freshman"),
        ("sophomore", "Sophomore"),
        ("junior", "Junior"),
        ("senior", "Senior"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile"
    )
    passport = models.CharField(max_length=100)
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES)
    language = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Select the country whose language you speak"),
    )

    def __str__(self):
        return f"{self.user.get_full_name()} – {self.stage}"


# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------
class Application(TimeStampedModel):
    class Meta:
        verbose_name = _("Application")
        verbose_name_plural = _("Applications")

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", _("In Progress")
        FINISHED = "finished", _("Finished")
        FAILED = "failed", _("Failed")

    class StepChoices(models.IntegerChoices):
        STEP_1 = 1, _("Step One")
        STEP_2 = 2, _("Step Two")
        STEP_3 = 3, _("Step Three")
        STEP_4 = 4, _("Step Four")
        STEP_5 = 5, _("Step Five")
        STEP_6 = 6, _("Step Six")
        STEP_7 = 7, _("Step Seven")

    STUDENT_TYPE_CHOICES = [
        ("transfer", _("Transfer Student")),
        ("first_year", _("First-Year Student")),
    ]

    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="agent_applications",
        limit_choices_to={"user_type": User.UserType.AGENT},
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_applications",
        limit_choices_to={"user_type": User.UserType.DEFAULT},
    )
    student_type = models.CharField(
        max_length=15, choices=STUDENT_TYPE_CHOICES, default="first_year"
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.IN_PROGRESS
    )
    step = models.IntegerField(choices=StepChoices.choices, default=StepChoices.STEP_1)
    application_name = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        help_text=_("Auto-generated application code"),
    )
    documents = models.FileField(
        upload_to=application_document_upload_to,
        blank=True,
        null=True,
        verbose_name=_("Application Documents"),
        validators=[validate_document_file_extension],
    )

    def save(self, *args, **kwargs):
        if not self.application_name:
            while True:
                code = get_random_string(10).upper()
                if not Application.objects.filter(application_name=code).exists():
                    self.application_name = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.username
        agent_name = self.agent.get_full_name() or self.agent.username
        return f"{self.application_name} – {student_name} (via {agent_name})"

    def get_absolute_url(self):
        return reverse("application_detail", args=[self.pk])


# 1. Global Site Settings (Singleton - managed by admin)
class SiteSettings(models.Model):
    whatsapp_number = models.CharField(max_length=20, default="+905344615317")
    email = models.EmailField(default="Matinf1060@gmail.com")
    address = models.CharField(max_length=255, blank=True)  # Translatable
    instagram_url = models.URLField(blank=True, null=True)
    telegram_url = models.URLField(blank=True, null=True)

    # Hero Section
    hero_title = models.CharField(
        max_length=200, default="Unlock Your Fully Funded Future."
    )  # Translatable
    hero_subtitle = models.CharField(max_length=500, blank=True)  # Translatable
    hero_background_image = models.ImageField(
        upload_to="home/", default="static/images/home/hero.jpg"
    )

    # Chat file-transfer policy. The default pre-fills the grant dialog; an
    # actual FilePermission row decides what a student may send. chat_max_
    # total_storage_mb is the site-wide ceiling over all chat uploads, so a
    # flood of grants cannot exhaust the disk either.
    chat_default_file_mb = models.PositiveIntegerField(
        default=5,
        help_text=_(
            "Default per-student file size limit (MB) pre-filled when a chat "
            "file permission is granted. Students without a grant cannot send "
            "files at all."
        ),
    )
    chat_max_total_storage_mb = models.PositiveIntegerField(
        default=1024,
        help_text=_(
            "Site-wide ceiling (MB) on the total size of all chat uploads. "
            "Uploads are refused once it is reached."
        ),
    )

    class Meta:
        verbose_name = _("Site Settings")
        verbose_name_plural = _("Site Settings")

    def __str__(self):
        return "Global Site Settings"


# 2. How It Works Steps (Dynamic number of steps)
class HowItWorksStep(models.Model):
    order = models.PositiveIntegerField(
        default=0, help_text="Display order (1, 2, 3...)"
    )
    icon_class = models.CharField(
        max_length=50, default="fas fa-star", help_text="FontAwesome class"
    )
    title = models.CharField(max_length=100)  # Translatable
    description = models.TextField()  # Translatable
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        verbose_name = _("Journey Step")

    def __str__(self):
        return f"Step {self.order}: {self.title}"


# 3. Document Requirements
class DocumentRequirement(models.Model):
    LEVEL_CHOICES = [
        ("associate_bachelor", _("Associate & Bachelor")),
        ("master", _("Master")),
        ("phd", _("PhD")),
    ]
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    title = models.CharField(max_length=200)  # Translatable
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["level", "order"]
        verbose_name = _("Document Requirement")

    def __str__(self):
        return f"{self.get_level_display()} - {self.title}"


# 4. Success Stories
class SuccessStory(models.Model):
    name = models.CharField(max_length=100)
    origin_country = models.CharField(max_length=50)  # Translatable
    destination_university = models.ForeignKey("University", on_delete=models.CASCADE)
    degree_level = models.CharField(max_length=50)  # Translatable
    quote = models.TextField()  # Translatable
    image = models.ImageField(
        upload_to="success_stories/",
        blank=True,
        null=True,
        help_text="Student photo for the homepage story card. Falls back to an initial avatar when empty.",
    )
    instagram_video_url = models.URLField(
        blank=True, null=True, help_text="Link to the Instagram video"
    )
    is_published = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Success Story")
        verbose_name_plural = _("Success Stories")

    def __str__(self):
        return self.name


class UserInfo(models.Model):
    pass


class Notification(models.Model):
    """
    Admin-sent notifications to users.
    Each notification can target:
      - all users
      - a specific user type group (default/company/agent)
      - specific individual users
    """

    class NotificationType(models.TextChoices):
        INFO = "info", _("Information")
        WARNING = "warning", _("Warning")
        SUCCESS = "success", _("Success")
        ERROR = "error", _("Error")
        REMINDER = "reminder", _("Reminder")

    class RecipientType(models.TextChoices):
        ALL_USERS = "all", _("All Users")
        DEFAULT_USERS = "default", _("Students (Default)")
        COMPANY_USERS = "company", _("Company Users")
        AGENT_USERS = "agent", _("Agent Users")
        SPECIFIC_USERS = "specific", _("Specific Users")

    title = models.CharField(max_length=255, verbose_name=_("Title"))
    message = models.TextField(verbose_name=_("Message"))
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        verbose_name=_("Notification Type"),
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RecipientType.choices,
        default=RecipientType.ALL_USERS,
        verbose_name=_("Recipient Type"),
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_notifications",
        verbose_name=_("Sent By"),
    )
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="NotificationRecipient",
        related_name="received_notifications",
        verbose_name=_("Recipients"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    def __str__(self):
        return f"{self.title} ({self.get_notification_type_display()})"

    def get_recipients_queryset(self):
        """Return the actual User queryset targeted by this notification."""
        from core.models import User

        if self.recipient_type == self.RecipientType.ALL_USERS:
            return User.objects.filter(is_active=True)
        elif self.recipient_type == self.RecipientType.DEFAULT_USERS:
            return User.objects.filter(user_type="default", is_active=True)
        elif self.recipient_type == self.RecipientType.COMPANY_USERS:
            return User.objects.filter(user_type="company", is_active=True)
        elif self.recipient_type == self.RecipientType.AGENT_USERS:
            return User.objects.filter(user_type="agent", is_active=True)
        elif self.recipient_type == self.RecipientType.SPECIFIC_USERS:
            return User.objects.filter(received_notifications=self)
        return User.objects.none()


class NotificationRecipient(models.Model):
    """
    Through model linking a Notification to a User, tracking read status.
    """

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    is_read = models.BooleanField(default=False, verbose_name=_("Read"))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Read At"))

    class Meta:
        unique_together = ("notification", "user")
        verbose_name = _("Notification Recipient")
        verbose_name_plural = _("Notification Recipients")

    def __str__(self):
        return f"{self.user.username} - {self.notification.title}"


# ---------------------------------------------------------------------------
# Chat (1-to-1 messaging: admin ↔ everyone, agent/company ↔ their students)
# ---------------------------------------------------------------------------


def chat_file_upload_to(instance, filename):
    """Per-attachment upload path: ``chat/<conversation>/<message>/name``.

    The folder ids come from the owning message, because ``upload_to`` runs
    while the attachment row is still being inserted (``instance.pk`` is None
    at that point) and an attachment itself only knows its message.
    """
    safe_name = os.path.basename(filename)
    message = instance.message
    conversation_id = message.conversation_id if message is not None else 0
    message_id = message.pk if message is not None else 0
    return f"chat/{conversation_id}/{message_id or 0}/{safe_name}"


class Conversation(TimeStampedModel):
    """A 1-to-1 chat thread, identified by the ordered user pair.

    Storing ``(user_low, user_high)`` with ``user_low.pk < user_high.pk`` gives
    every pair exactly one row regardless of who opened it first; all message,
    read and pin state hangs off that row, so both parties always see the same
    thread.
    """

    user_low = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversations_low"
    )
    user_high = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conversations_high"
    )
    # Denormalized for the conversations list ordering; maintained by touch().
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = _("Chat conversation")
        verbose_name_plural = _("Chat conversations")
        constraints = [
            models.UniqueConstraint(
                fields=["user_low", "user_high"], name="chat_pair_unique"
            )
        ]
        indexes = [
            models.Index(fields=["user_low", "last_message_at"]),
            models.Index(fields=["user_high", "last_message_at"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.user_low_id}<->{self.user_high_id}"

    def both_users(self):
        """The two people in the thread, low first.

        Named for the pair rather than ``participants`` on purpose: the reverse
        accessor of ConversationParticipant.conversation (``participants``, the
        per-user state rows) already owns that attribute, and Django's related
        manager descriptor would silently replace this method if the names
        collided.
        """
        return [self.user_low, self.user_high]

    def is_participant(self, user):
        return user.pk in (self.user_low_id, self.user_high_id)

    def partner_of(self, user):
        """The other participant, from ``user``'s perspective."""
        return self.user_high if self.user_low_id == user.pk else self.user_low

    def touch(self):
        """Refresh list ordering after a message lands."""
        self.last_message_at = timezone.now()
        self.save(update_fields=["last_message_at"])


class ConversationParticipant(models.Model):
    """Per-participant chat state: read marker, presence, typing.

    Split from Conversation so one participant's read marker or presence flag
    never writes the row the other is reading.
    """

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_participations"
    )
    # Read receipts: a message shows the double check when the peer's
    # last_read_at is at or after the message's timestamp (Telegram's model).
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    is_typing = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Chat participant")
        verbose_name_plural = _("Chat participants")
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="chat_participant_unique"
            )
        ]

    def __str__(self):
        return f"{self.user_id}@conv{self.conversation_id}"


class MessageAttachment(TimeStampedModel):
    """One uploaded file on a chat message.

    Kept off Message so a text message is a single-row insert and the site-wide
    storage accounting is a cheap aggregate over this table.
    """

    message = models.ForeignKey(
        "Message", on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=chat_file_upload_to, max_length=500)
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=100, blank=True)
    is_image = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Chat attachment")
        verbose_name_plural = _("Chat attachments")

    def __str__(self):
        return self.original_name


class Message(TimeStampedModel):
    """One chat message. Never hard-deleted: ``is_deleted`` hides it."""

    class Meta:
        verbose_name = _("Chat message")
        verbose_name_plural = _("Chat messages")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="chat_messages_sent"
    )
    body = models.TextField(blank=True)

    # Soft delete: row and file stay in the database; the UI shows a
    # placeholder. deleted_by records which side hid it.
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages_deleted",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_edited = models.BooleanField(default=False)

    # One pinned message per conversation (Telegram-style single pin).
    is_pinned = models.BooleanField(default=False)

    # Forwarding keeps a pointer to the origin for the "Forwarded" label; the
    # label survives even if the origin is later deleted.
    forwarded_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forwards",
    )

    # Replies quote their parent; deleting the parent leaves the reply showing
    # the standard "deleted" placeholder.
    reply_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies"
    )

    def __str__(self):
        preview = (self.body or "")[:30] or ("file" if self.has_file else "")
        return f"{self.sender_id}: {preview}"

    @property
    def has_file(self):
        return self.attachments.exists()

    def can_modify(self, user):
        """Only the sender edits, pins or deletes-for-everyone their message."""
        return self.sender_id == user.pk

    def soft_delete(self, user):
        """Hide for both parties. Only the sender can do this."""
        if not self.can_modify(user):
            raise PermissionError("Only the sender can delete a message")
        self.is_deleted = True
        self.deleted_by = user
        self.deleted_at = timezone.now()
        if self.is_pinned:
            self.is_pinned = False
        self.save(
            update_fields=[
                "is_deleted",
                "deleted_by",
                "deleted_at",
                "is_pinned",
                "updated_at",
            ]
        )


class FilePermission(models.Model):
    """Whether a student may attach files in chat, and how large.

    Without an active row a student cannot upload at all. With one, the
    allowance is ``min(max_file_mb, core.chat.CHAT_FILE_MAX_MB)`` — the grant
    dialog pre-fills the site default (SiteSettings.chat_default_file_mb) and
    may raise or lower it per student, but never above the hard ceiling.
    """

    student = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="chat_file_permission"
    )
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="chat_file_grants"
    )
    max_file_mb = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Chat file permission")
        verbose_name_plural = _("Chat file permissions")

    def __str__(self):
        state = "on" if self.is_active else "off"
        return f"{self.student_id}: {self.max_file_mb}MB ({state})"

    def clean(self):
        from core.chat import CHAT_FILE_MAX_MB

        if self.max_file_mb > CHAT_FILE_MAX_MB:
            raise ValidationError(
                {
                    "max_file_mb": _("Cannot exceed the %(ceiling)s MB ceiling.")
                    % {"ceiling": CHAT_FILE_MAX_MB}
                }
            )
        if self.max_file_mb < 1:
            raise ValidationError({"max_file_mb": _("Must be at least 1 MB.")})

    @classmethod
    def allowance_mb_for(cls, user):
        """The upload limit in MB for ``user``, or None when uploads are closed."""
        row = cls.objects.filter(student=user, is_active=True).first()
        if row is None:
            return None
        from core.chat import CHAT_FILE_MAX_MB

        return min(row.max_file_mb, CHAT_FILE_MAX_MB)

    @classmethod
    def default_allowance_mb(cls):
        """The site default from Site Settings, clamped to the hard ceiling.

        Used when a granter leaves the size field alone: the dialog pre-fills
        this value, and an API client that omits ``max_file_mb`` gets it too.
        """
        from core.chat import CHAT_FILE_MAX_MB

        site = SiteSettings.objects.get_or_create(pk=1)[0]
        return max(1, min(site.chat_default_file_mb, CHAT_FILE_MAX_MB))

    @classmethod
    def grant(cls, student, granted_by, max_file_mb=None):
        """Create or update the student's permission, returning (row, created)."""
        from core.chat import CHAT_FILE_MAX_MB

        if max_file_mb is None:
            max_file_mb = cls.default_allowance_mb()
        max_file_mb = max(1, min(int(max_file_mb), CHAT_FILE_MAX_MB))
        row, created = cls.objects.update_or_create(
            student=student,
            defaults={
                "granted_by": granted_by,
                "max_file_mb": max_file_mb,
                "is_active": True,
            },
        )
        return row, created
