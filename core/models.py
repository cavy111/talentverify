import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from cryptography.fernet import Fernet
import os

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------
# Store FIELD_ENCRYPTION_KEY in environment, never in source control.
# Generate with: Fernet.generate_key()
_fernet = None

def get_fernet():
    global _fernet
    if _fernet is None:
        key = os.environ.get("FIELD_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("FIELD_ENCRYPTION_KEY environment variable is not set.")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(value: str) -> str:
    """Encrypt a string value for storage."""
    if not value:
        return value
    return get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a stored encrypted value."""
    if not value:
        return value
    return get_fernet().decrypt(value.encode()).decode()


class EncryptedField(models.TextField):
    """
    Custom field that transparently encrypts on save and decrypts on load.
    WHY: PII fields (names, phone numbers, national IDs, addresses, emails)
    must be encrypted at rest so that a raw database dump does not expose
    sensitive personal information. This satisfies GDPR / POPIA requirements
    and limits blast radius if the DB server is compromised.
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt(value)

    def get_prep_value(self, value):
        if value is None:
            return value
        return encrypt(value)


# ---------------------------------------------------------------------------
# Custom user manager & model
# ---------------------------------------------------------------------------

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Platform user. Three roles are supported via is_staff / role field:
      - TALENT_VERIFY_ADMIN : Anthropic / Talent Verify internal staff
      - COMPANY_ADMIN       : HR admin for a specific company
      - COMPANY_USER        : Read-only or limited company staff
    """

    ROLE_CHOICES = [
        ("tv_admin", "Talent Verify Admin"),
        ("company_admin", "Company Admin"),
        ("company_user", "Company User"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="company_user")
    company = models.ForeignKey(
        "Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
        help_text="Null for Talent Verify admins.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


# ---------------------------------------------------------------------------
# Company & Department
# ---------------------------------------------------------------------------

class Company(models.Model):
    """
    Represents an employer registered on the Talent Verify platform.

    Encrypted fields (WHY):
      - address            : physical location is PII under POPIA / GDPR
      - contact_phone      : direct personal contact info
      - email              : contact email may identify an individual
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    registration_date = models.DateField(null=True, blank=True)
    registration_number = models.CharField(max_length=100, unique=True, db_index=True)
    address = EncryptedField(
        blank=True,
        help_text="Encrypted at rest — physical address is PII."
    )
    contact_person = models.CharField(max_length=255, blank=True)
    contact_phone = EncryptedField(
        blank=True,
        help_text="Encrypted at rest — direct phone number is PII."
    )
    email = EncryptedField(
        blank=True,
        help_text="Encrypted at rest — contact email is PII."
    )
    employee_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("company", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} — {self.company.name}"


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

class Employee(models.Model):
    """
    A person who has been (or is currently) employed by one or more companies.

    Encrypted fields (WHY):
      - first_name / last_name : personal identity — core PII
      - national_id            : government-issued identifier — highest-risk PII;
                                 breach enables identity theft
    employee_id_number is stored plaintext because companies need to look up
    records by their own internal ID without decrypting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = EncryptedField(help_text="Encrypted — personal identity PII.")
    last_name = EncryptedField(help_text="Encrypted — personal identity PII.")
    employee_id_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Company-assigned ID. Stored plaintext for lookup performance.",
    )
    national_id = EncryptedField(
        blank=True,
        help_text="Encrypted — government ID is highest-risk PII.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Search support: store a salted hash of (first_name + last_name) so that
    # exact-match searches work without decrypting every row.
    name_search_hash = models.CharField(max_length=64, blank=True, db_index=True)

    def __str__(self):
        return f"{decrypt(self.first_name)} {decrypt(self.last_name)}"


# ---------------------------------------------------------------------------
# Employment record (role history)
# ---------------------------------------------------------------------------

class EmploymentRecord(models.Model):
    """
    Links an Employee to a Company for a specific role and time period.
    One employee may have many records (promotions, transfers, company changes).
    This is the core history table — never delete, only mark date_left.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="employment_records")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employment_records")
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employment_records",
    )
    role_title = models.CharField(max_length=255, db_index=True)
    date_started = models.DateField(db_index=True)
    date_left = models.DateField(null=True, blank=True, db_index=True)
    is_current = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_started"]

    def __str__(self):
        status = "current" if self.is_current else str(self.date_left)
        return f"{self.employee} @ {self.company} — {self.role_title} ({status})"

    def save(self, *args, **kwargs):
        # Auto-set is_current based on date_left
        if self.date_left:
            self.is_current = False
        super().save(*args, **kwargs)


class RoleDuty(models.Model):
    """
    Individual duty/responsibility for a given employment record.
    Stored separately to allow flexible, unbounded lists of duties.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employment_record = models.ForeignKey(
        EmploymentRecord, on_delete=models.CASCADE, related_name="duties"
    )
    duty_description = models.TextField()

    def __str__(self):
        return self.duty_description[:80]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    """
    Immutable audit trail for all create / update / delete operations.
    WHY: Required for security compliance, breach investigation, and
    demonstrating data integrity to verifying parties. Entries must never
    be updated or deleted — enforce this via DB-level permissions on the table.
    """

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("bulk_upload", "Bulk Upload"),
        ("login", "Login"),
        ("failed_login", "Failed Login"),
        ("export", "Export"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    table_affected = models.CharField(max_length=100)
    record_id = models.UUIDField(null=True, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        # DB admin should grant INSERT-only permission on this table to the
        # application DB user — no UPDATE or DELETE.

    def __str__(self):
        return f"{self.action} on {self.table_affected} by {self.actor} at {self.timestamp}"
