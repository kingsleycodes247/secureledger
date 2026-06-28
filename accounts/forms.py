"""
accounts/forms.py
─────────────────
All authentication & profile forms for SecureLedger.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from .models import User, UserProfile


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

class RegisterForm(forms.ModelForm):
    first_name    = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'First name', 'class': 'form-input'}))
    last_name     = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'placeholder': 'Last name', 'class': 'form-input'}))
    username      = forms.CharField(max_length=40, widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-input'}))
    email         = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email address', 'class': 'form-input'}))
    phone         = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'placeholder': '+1 (415) 000-0000', 'class': 'form-input'}))
    country       = forms.CharField(max_length=100, widget=forms.Select(attrs={'class':'form-input'}))
    password1     = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Create a strong password', 'class': 'form-input', 'id': 'pw1'}),
    )
    password2     = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat your password', 'class': 'form-input', 'id': 'pw2'}),
    )
    referral_code = forms.CharField(max_length=12, required=False, widget=forms.TextInput(attrs={'placeholder': 'Referral code (optional)', 'class': 'form-input'}))
    terms         = forms.BooleanField(error_messages={'required': 'You must agree to the terms to continue.'})

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'country']

    # ── Custom validation ─────────────────────────────────────────────────────
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean_password1(self):
        pw = self.cleaned_data.get('password1')
        if pw:
            password_validation.validate_password(pw)
        return pw

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('password1')
        pw2 = cleaned.get('password2')
        if pw1 and pw2 and pw1 != pw2:
            self.add_error('password2', 'Passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_active = True  # Active but email NOT verified yet
        user.is_email_verified = False
        if commit:
            user.save()
            # Handle referral
            ref_code = self.cleaned_data.get('referral_code', '').strip().upper()
            if ref_code:
                try:
                    referrer = User.objects.get(referral_code=ref_code)
                    user.referred_by = referrer
                    user.save()
                except User.DoesNotExist:
                    pass
        return user


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────
class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email address',
            'class': 'form-input',
            'autocomplete': 'email',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'form-input',
            'autocomplete': 'current-password',
            'id': 'loginPw',
        }),
    )

    error_messages = {
        'invalid_login': 'Incorrect email or password. Please try again.',
        'inactive': 'This account has been disabled.',
    }


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset Request
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your registered email',
            'class': 'form-input',
            'id': 'reset-email',
        }),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if not User.objects.filter(email=email, is_active=True).exists():
            # Deliberately vague for security
            raise ValidationError('If this email exists, a reset link has been sent.')
        return email


# ─────────────────────────────────────────────────────────────────────────────
# Set New Password (after reset)
# ─────────────────────────────────────────────────────────────────────────────
class SetNewPasswordForm(forms.Form):
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New password', 'class': 'form-input', 'id': 'new-pw'}),
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password', 'class': 'form-input', 'id': 'confirm-pw'}),
    )

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Passwords do not match.')
        if p1:
            password_validation.validate_password(p1)
        return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Profile Update
# ─────────────────────────────────────────────────────────────────────────────
class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-input'}))
    last_name  = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-input'}))
    phone      = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    country    = forms.CharField(max_length=100, widget=forms.Select(attrs={'class':'form-input'}))

    class Meta:
        model  = UserProfile
        fields = ['avatar', 'bio', 'date_of_birth', 'address', 'city', 'zip_code', 'email_notifications', 'sms_notifications']
        widgets = {
            'bio':           forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'address':       forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'city':          forms.TextInput(attrs={'class': 'form-input'}),
            'zip_code':      forms.TextInput(attrs={'class': 'form-input'}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Password Change (authenticated)
# ─────────────────────────────────────────────────────────────────────────────
class PasswordUpdateForm(PasswordChangeForm):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Current password'}),
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'New password', 'id': 'new-pw'}),
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm new password'}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Support Ticket
# ─────────────────────────────────────────────────────────────────────────────
class SupportTicketForm(forms.Form):
    SUBJECT_CHOICES = [
        ('', 'Select a subject'),
        ('investment',  'Investment Enquiry'),
        ('withdrawal',  'Withdrawal Issue'),
        ('deposit',     'Deposit Issue'),
        ('recovery',    'Asset Recovery'),
        ('account',     'Account Issue'),
        ('referral',    'Referral Bonus'),
        ('other',       'Other'),
    ]
    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
        ('urgent', 'Urgent'),
    ]

    subject  = forms.ChoiceField(choices=SUBJECT_CHOICES, widget=forms.Select(attrs={'class': 'form-input'}))
    priority = forms.ChoiceField(choices=PRIORITY_CHOICES, widget=forms.Select(attrs={'class': 'form-input'}))
    message  = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 5, 'placeholder': 'Describe your issue in detail…'}),
    )
