import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings


class InvestmentPlan(models.Model):
    """
    The 5 fixed plans.  Seed these via a data migration or the admin.
    """
    PLAN_NAMES = [
        ('bronze',  'Bronze Plan'),
        ('silver',  'Silver Plan'),
        ('gold',    'Gold Plan'),
        ('diamond', 'Diamond Plan'),
        ('mining',  'Mining Plan'),
    ]

    name = models.CharField(max_length=20, choices=PLAN_NAMES, unique=True)
    label = models.CharField(max_length=60)          # e.g. "3.2% DAILY FOR 7 DAYS"
    daily_return_pct = models.DecimalField(max_digits=6, decimal_places=2)  # e.g. 3.20
    duration_days = models.PositiveIntegerField()
    min_deposit = models.DecimalField(max_digits=18, decimal_places=2)
    max_deposit = models.DecimalField(max_digits=18, decimal_places=2)
    referral_bonus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('10.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['min_deposit']

    def __str__(self):
        return f'{self.get_name_display()} — {self.daily_return_pct}% / {self.duration_days}d'

    def expected_profit(self, amount: Decimal) -> Decimal:
        return (amount * self.daily_return_pct / 100 * self.duration_days).quantize(Decimal('0.01'))

    def expected_total(self, amount: Decimal) -> Decimal:
        return amount + self.expected_profit(amount)


class CompanyWallet(models.Model):
    CRYPTO_CHOICES = [
        ('BTC',  'Bitcoin'),
        ('USDT', 'Tether USDT'),
        ('ETH',  'Ethereum'),
        ('SOL',  'Solana'),
    ]
    crypto = models.CharField(max_length=10, choices=CRYPTO_CHOICES, unique=True)
    network = models.CharField(max_length=50, blank=True)   # e.g. "TRC20", "ERC20"
    address = models.CharField(max_length=200)
    qr_code = models.ImageField(upload_to='wallet_qr/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.get_crypto_display()} — {self.address[:16]}…'
    

class Investment(models.Model):
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('active',    'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='investments',
    )
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT, related_name='investments')
    investment_id = models.CharField(max_length=14, unique=True, editable=False)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    expected_profit = models.DecimalField(max_digits=18, decimal_places=2)
    expected_total = models.DecimalField(max_digits=18, decimal_places=2)
    payment_method = models.CharField(max_length=20)   # BTC / USDT / ETH / SOL
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    profit_credited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    proof_of_payment = models.ImageField(upload_to='deposit_proofs/', blank=True, null=True)
    proof_uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.investment_id} — {self.user.email} — {self.plan.get_name_display()}'

    def save(self, *args, **kwargs):
        if not self.investment_id:
            self.investment_id = f'SLI-{uuid.uuid4().hex[:8].upper()}'
        if not self.expected_profit:
            self.expected_profit = self.plan.expected_profit(self.amount)
        if not self.expected_total:
            self.expected_total = self.plan.expected_total(self.amount)
        super().save(*args, **kwargs)

    def activate(self):
        self.status = 'active'
        self.start_date = timezone.now()
        self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        self.save()

    @property
    def days_remaining(self):
        if self.status != 'active' or not self.end_date:
            return 0
        delta = self.end_date - timezone.now()
        return max(0, delta.days)

    @property
    def progress_pct(self):
        if self.status != 'active' or not self.start_date or not self.end_date:
            return 0
        total = (self.end_date - self.start_date).total_seconds()
        elapsed = (timezone.now() - self.start_date).total_seconds()
        return min(100, round(elapsed / total * 100, 1))


class Transaction(models.Model):
    TX_TYPES = [
        ('deposit',         'Deposit'),
        ('withdrawal',      'Withdrawal'),
        ('profit',          'Profit'),
        ('bonus',           'Bonus'),
        ('referral_bonus',  'Referral Bonus'),
    ]
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    transaction_id = models.CharField(max_length=16, unique=True, editable=False)
    tx_type = models.CharField(max_length=20, choices=TX_TYPES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_method = models.CharField(max_length=30, blank=True)
    wallet_address = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True)
    investment = models.ForeignKey(
        Investment, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_id} — {self.tx_type} — ${self.amount}'

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f'SLT-{uuid.uuid4().hex[:9].upper()}'
        super().save(*args, **kwargs)
