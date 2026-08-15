# core/models.py
import os

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import JSONField
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


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
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Allowed: .jpg, .jpeg, .png, .gif, .webp'))


def validate_document_file_extension(value):
    valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(_('Unsupported file extension. Allowed: .pdf, .doc, .docx, .jpg, .jpeg, .png'))


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
        max_length=100,
        help_text=_("Primary language"),
        blank=True,
        null=True
    )
    nationality = models.CharField(
        max_length=100,
        help_text=_("Nationality adjective"),
        blank=True,
        null=True
    )

    class Meta:
        verbose_name_plural = "Countries"
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='country_name_ci_unique'
            )
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
        unique_together = ("country", "name")

    def __str__(self):
        return f"{self.name}, {self.country.name}"


class TermOption(TimeStampedModel):
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label


class YearOption(TimeStampedModel):
    VALUE_CHOICES = [
        ('1', '1'),
        ('1.5', '1.5'),
        ('2', '2'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
    ]
    value = models.CharField(
        max_length=10,
        choices=VALUE_CHOICES,
        unique=True,
        help_text=_("Number of years—for example, '1', '1.5', '2', etc.")
    )

    def __str__(self):
        return self.get_value_display()


class Faculty(TimeStampedModel):
    name = models.CharField(max_length=200)
    year_options = models.ManyToManyField(
        YearOption,
        blank=True,
        related_name="faculties",
        help_text=_("Select one or more possible durations (in years) that this faculty offers.")
    )

    def __str__(self):
        return self.name


class University(TimeStampedModel):
    SECTOR_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('other', 'Other'),
    ]

    external_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text=_("ID from info.studyfans.com")
    )

    name = models.CharField(max_length=255, unique=True)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='universities'
    )
    city = models.ForeignKey(
        City, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='universities'
    )
    address = models.CharField(max_length=500, blank=True)
    website = models.URLField(blank=True, null=True)

    parsed_data = JSONField(
        default=dict,
        blank=True,
        help_text=_("Parsed details (dates, exams, documents, fees, etc.) from the site")
    )

    sector = models.CharField(
        max_length=20, choices=SECTOR_CHOICES, default='private'
    )
    founded_in = models.PositiveIntegerField(
        blank=True, null=True,
        help_text=_("Year founded, e.g. 2013")
    )
    main_campus = models.CharField(max_length=255, blank=True)
    pin_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_("University PIN code")
    )
    faculties = models.ManyToManyField(
        Faculty,
        blank=True,
        related_name='universities'
    )
    available_languages = models.ManyToManyField(
        Country,
        blank=True,
        related_name='language_universities',
        help_text=_("Which country languages are taught/used by this university")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('name'), name='university_name_ci_unique')
        ]

    def __str__(self):
        return self.name


class Program(TimeStampedModel):
    class StatusChoices(models.TextChoices):
        AVAILABLE = 'available', _("Available")
        NEAR_TO_CLOSE = 'near_to_close', _("Near to Close")
        QUOTA_FULL = 'quota_full', _("Quota Full")
        CLOSED = 'closed', _("Closed")

    DEGREE_CHOICES = [
        ('associate', 'Associate'),
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('phd', 'PhD'),
        ('integrated_phd', 'Integrated PhD'),
    ]

    external_id = models.IntegerField(unique=True, null=True, blank=True, help_text=_("ID from info.studyfans.com"))

    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=15,
        choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE
    )
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name='programs'
    )
    faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='programs'
    )
    degree = models.CharField(
        max_length=20,
        choices=DEGREE_CHOICES
    )
    duration = models.CharField(
        max_length=10,
        choices=YearOption.VALUE_CHOICES,
        blank=True,
        help_text=_("Duration in years; should be one of the faculty's year options")
    )
    deposit_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prep_school_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    semester_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Fee per semester")
    )
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    offer = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_("Scholarship or discount offered")
    )
    term = models.ForeignKey(
        TermOption, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.name} @ {self.university.name}"


# -----------------------------------------------------------------------------
# Custom User + Profiles
# -----------------------------------------------------------------------------
class User(AbstractUser):
    class UserType(models.TextChoices):
        DEFAULT = 'default', _("Default")
        COMPANY = 'company', _("Company")
        AGENT = 'agent', _("Agent")

    class GenderChoices(models.TextChoices):
        MALE = 'male', _("Male")
        FEMALE = 'female', _("Female")

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.DEFAULT
    )
    gender = models.CharField(
        max_length=10,
        choices=GenderChoices.choices,
        blank=True,
        null=True
    )
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="origin_users"
    )
    city = models.ForeignKey(
        City, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="origin_city_users"
    )
    date_of_birth = models.DateField(blank=True, null=True)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    citizenship = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="citizens"
    )
    mobile = models.CharField(max_length=20, blank=True, null=True)
    profile_image = models.ImageField(
        upload_to=user_profile_image_path,
        null=True,
        blank=True,
        verbose_name=_("Profile Image"),
        help_text=_("Upload a profile image (max 2MB)"),
        validators=[validate_image_file_extension]
    )
    is_representative = models.BooleanField(
        default=False,
        help_text=_("Designates whether this student can access representative features")
    )

    def __str__(self):
        return self.get_username()

    def clean(self):
        # Student representatives must be student users
        if self.is_representative and self.user_type != User.UserType.DEFAULT:
            raise ValidationError(_("Only student users can be representatives"))


class CompanyProfile(TimeStampedModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='company_profile'
    )
    company_name = models.CharField(max_length=255)
    company_email = models.EmailField()
    tax_number = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    website = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.company_name


class AgentProfile(TimeStampedModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='agent_profile'
    )
    agency = models.ForeignKey(
        CompanyProfile, on_delete=models.CASCADE, related_name='agents'
    )

    def __str__(self):
        return f"{self.user.get_full_name()} (Agent of {self.agency.company_name})"


class StudentProfile(TimeStampedModel):
    STAGE_CHOICES = [
        ('freshman', 'Freshman'),
        ('sophomore', 'Sophomore'),
        ('junior', 'Junior'),
        ('senior', 'Senior'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='student_profile'
    )
    passport = models.CharField(max_length=100)
    stage = models.CharField(max_length=50, choices=STAGE_CHOICES)
    language = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        help_text=_("Select the country whose language you speak")
    )

    def __str__(self):
        return f"{self.user.get_full_name()} – {self.stage}"


# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------
class Application(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', _("In Progress")
        FINISHED = 'finished', _("Finished")
        FAILED = 'failed', _("Failed")

    class StepChoices(models.IntegerChoices):
        STEP_1 = 1, _("Step One")
        STEP_2 = 2, _("Step Two")
        STEP_3 = 3, _("Step Three")
        STEP_4 = 4, _("Step Four")
        STEP_5 = 5, _("Step Five")
        STEP_6 = 6, _("Step Six")
        STEP_7 = 7, _("Step Seven")

    STUDENT_TYPE_CHOICES = [
        ('transfer', _("Transfer Student")),
        ('first_year', _("First-Year Student")),
    ]

    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='agent_applications',
        limit_choices_to={'user_type': User.UserType.AGENT}
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='student_applications',
        limit_choices_to={'user_type': User.UserType.DEFAULT}
    )
    student_type = models.CharField(
        max_length=15,
        choices=STUDENT_TYPE_CHOICES,
        default='first_year'
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applications'
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.IN_PROGRESS
    )
    step = models.IntegerField(
        choices=StepChoices.choices,
        default=StepChoices.STEP_1
    )
    application_name = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        help_text=_("Auto-generated application code")
    )
    documents = models.FileField(
        upload_to=application_document_upload_to,
        blank=True,
        null=True,
        verbose_name=_("Application Documents"),
        validators=[validate_document_file_extension]
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
        return reverse('application_detail', args=[self.pk])
