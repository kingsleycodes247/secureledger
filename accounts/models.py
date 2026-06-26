import uuid
import random
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings


# ─────────────────────────────────────────────────────────────────────────────
# Custom User
# ─────────────────────────────────────────────────────────────────────────────
class User(AbstractUser):
    """
    Extended user: email is the login identifier; username kept for admin.
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Email verification
    is_email_verified = models.BooleanField(default=False)

    # Referral
    referral_code = models.CharField(max_length=12, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.get_full_name()} <{self.email}>'

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.get_full_name() or self.email

    @property
    def account_tier(self):
        """Return tier based on total deposits."""
        total = self.profile.total_deposit
        if total >= Decimal('35000'):
            return 'Mining Investor'
        elif total >= Decimal('20000'):
            return 'Diamond Investor'
        elif total >= Decimal('6000'):
            return 'Gold Investor'
        elif total >= Decimal('1000'):
            return 'Silver Investor'
        return 'Bronze Investor'


# ─────────────────────────────────────────────────────────────────────────────
# User Profile  (one-to-one with User)
# ─────────────────────────────────────────────────────────────────────────────
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)

    # ── Financial summary (computed from Investment / Transaction records) ──
    account_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_profit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_bonus = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_referral_bonus = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_deposit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_withdrawal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))

    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profile – {self.user.email}'

    @property
    def total_investments(self):
        return self.user.investments.count()

    @property
    def active_investments(self):
        return self.user.investments.filter(status='active').count()

    @property
    def locked_balance(self):
        """Capital currently tied up in pending or active investments."""
        from decimal import Decimal
        from django.db.models import Sum
        total = self.user.investments.filter(
            status__in=['pending', 'active']
        ).aggregate(t=Sum('amount'))['t']
        return total or Decimal('0.00')

    @property
    def available_balance(self):
        """Money the user can actually withdraw (balance minus locked capital)."""
        from decimal import Decimal
        avail = self.account_balance - self.locked_balance
        return avail if avail > Decimal('0') else Decimal('0.00')
    
    
# ─────────────────────────────────────────────────────────────────────────────
# Email Verification Token
# ─────────────────────────────────────────────────────────────────────────────
class EmailVerificationToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'VerifyToken({self.user.email})'

    def is_valid(self):
        ttl = getattr(settings, 'EMAIL_VERIFICATION_TIMEOUT', 86400)
        return (timezone.now() - self.created_at).total_seconds() < ttl

    def refresh(self):
        self.token = uuid.uuid4()
        self.created_at = timezone.now()
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Token
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f'ResetToken({self.user.email})'

    def is_valid(self):
        if self.used:
            return False
        ttl = 60 * 60  # 1 hour
        return (timezone.now() - self.created_at).total_seconds() < ttl


# ─────────────────────────────────────────────────────────────────────────────
# Support Ticket
# ─────────────────────────────────────────────────────────────────────────────
class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    ticket_id = models.CharField(max_length=12, unique=True, editable=False)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    admin_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'#{self.ticket_id} – {self.subject}'

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f'SL-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Login OTP (One-Time Password) For User Login
# ─────────────────────────────────────────────────────────────────────────────
class LoginOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='login_otp')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)
    attempts = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'OTP({self.user.email})'

    def generate(self):
        self.code = f'{random.randint(0, 999999):06d}'
        self.attempts = 0
        self.save()
        return self.code

    def is_valid(self):
        # 10-minute expiry
        return (timezone.now() - self.created_at).total_seconds() < 600
    

# ─────────────────────────────────────────────────────────────────────────────
# Django signals – auto-create UserProfile
# ─────────────────────────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
