from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import User, EmailVerificationToken, PasswordResetToken
from .forms import (
    RegisterForm, LoginForm,
    PasswordResetRequestForm, SetNewPasswordForm,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _send_verification_email(request, user):
    """Create / refresh a token and dispatch the verification email."""
    token_obj, _ = EmailVerificationToken.objects.get_or_create(user=user)
    token_obj.refresh()

    verify_url = request.build_absolute_uri(
        reverse('accounts:verify_email', kwargs={'token': str(token_obj.token)})
    )

    subject = 'Verify your SecureLedger account'
    html_body = render_to_string('emails/verify_email.html', {
        'user': user,
        'verify_url': verify_url,
        'expiry_hours': 24,
    })
    plain_body = (
        f'Hi {user.first_name},\n\n'
        f'Please verify your SecureLedger account by visiting:\n{verify_url}\n\n'
        f'This link expires in 24 hours.\n\nThe SecureLedger Team'
    )

    send_mail(
        subject=subject,
        message=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )


def _send_password_reset_email(request, user, token_obj):
    reset_url = request.build_absolute_uri(
        reverse('accounts:password_reset_confirm', kwargs={'token': str(token_obj.token)})
    )
    subject = 'Reset your SecureLedger password'
    html_body = render_to_string('emails/password_reset.html', {
        'user': user,
        'reset_url': reset_url,
    })
    plain_body = (
        f'Hi {user.first_name},\n\n'
        f'Reset your password here:\n{reset_url}\n\n'
        f'This link expires in 1 hour.\n\nThe SecureLedger Team'
    )
    send_mail(subject, plain_body, settings.DEFAULT_FROM_EMAIL,
              [user.email], html_message=html_body, fail_silently=False)


# ─────────────────────────────────────────────────────────────────────────────
# Register
# ─────────────────────────────────────────────────────────────────────────────
class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                _send_verification_email(request, user)
            except Exception as e:
                import traceback; traceback.print_exc()   # full traceback
                # Log but don't crash registration
                #print(f'Email send failed: {e}')
            messages.success(
                request,
                f'Account created! Check {user.email} for a verification link.'
            )
            return redirect('accounts:registration_pending')
        # Re-render with errors
        return render(request, self.template_name, {'form': form})


# ─────────────────────────────────────────────────────────────────────────────
# Registration Pending (email sent notice)
# ─────────────────────────────────────────────────────────────────────────────
def registration_pending(request):
    return render(request, 'accounts/registration_pending.html')


# ─────────────────────────────────────────────────────────────────────────────
# Email Verification
# ─────────────────────────────────────────────────────────────────────────────
def verify_email(request, token):
    token_obj = get_object_or_404(EmailVerificationToken, token=token)

    if token_obj.user.is_email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('accounts:login')

    if not token_obj.is_valid():
        return render(request, 'accounts/verify_expired.html', {'user_email': token_obj.user.email})

    user = token_obj.user
    user.is_email_verified = True
    user.save()
    token_obj.delete()

    return render(request, 'accounts/verified.html', {'user': user})


# ─────────────────────────────────────────────────────────────────────────────
# Resend Verification
# ─────────────────────────────────────────────────────────────────────────────
def resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()
        try:
            user = User.objects.get(email=email, is_email_verified=False)
            _send_verification_email(request, user)
            messages.success(request, f'Verification email resent to {email}.')
        except User.DoesNotExist:
            messages.error(request, 'No unverified account found with that email.')
    return redirect('accounts:registration_pending')


# ─────────────────────────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────────────────────────
from .models import LoginOTP

def _send_login_otp(user):
    otp, _ = LoginOTP.objects.get_or_create(user=user)
    code = otp.generate()
    html_body = render_to_string('emails/login_otp.html', {'user': user, 'code': code})
    send_mail(
        subject='Your SecureLedger login code',
        message=f'Hi {user.first_name}, your login code is: {code}\nIt expires in 10 minutes.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )


class LoginView(View):
    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return render(request, self.template_name, {'form': LoginForm(request)})

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            if not user.is_email_verified:
                messages.warning(request, 'Please verify your email before logging in.')
                return redirect('accounts:registration_pending')

            # Don't log in yet — stash the user id and trigger OTP step
            request.session['pending_user_id'] = user.id
            request.session['remember'] = bool(request.POST.get('remember'))
            try:
                _send_login_otp(user)
            except Exception:
                import traceback; traceback.print_exc()
                messages.error(request, 'Could not send your login code. Try again.')
                return render(request, self.template_name, {'form': form})

            # Tell the template to open the 2FA modal
            return render(request, self.template_name, {'form': form, 'show_otp': True, 'otp_email': user.email})

        return render(request, self.template_name, {'form': form})


def verify_login_otp(request):
    if request.method != 'POST':
        return redirect('accounts:login')

    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please log in again.')
        return redirect('accounts:login')

    code = request.POST.get('otp_code', '').strip()
    try:
        user = User.objects.get(id=user_id)
        otp = user.login_otp
    except (User.DoesNotExist, LoginOTP.DoesNotExist):
        messages.error(request, 'Something went wrong. Please log in again.')
        return redirect('accounts:login')

    otp.attempts += 1
    otp.save()

    if otp.attempts > 5:
        messages.error(request, 'Too many attempts. Please log in again.')
        request.session.pop('pending_user_id', None)
        return redirect('accounts:login')

    if not otp.is_valid():
        messages.error(request, 'Your code expired. Please log in again.')
        return redirect('accounts:login')

    if code != otp.code:
        # Re-show modal with error
        return render(request, 'accounts/login.html', {
            'form': LoginForm(request), 'show_otp': True,
            'otp_email': user.email, 'otp_error': 'Invalid code. Please try again.',
        })

    # Success — log in
    login(request, user)
    otp.delete()
    if not request.session.get('remember'):
        request.session.set_expiry(0)   # browser-close session
    request.session.pop('pending_user_id', None)
    request.session.pop('remember', None)
    return redirect('dashboard:home')


def resend_login_otp(request):
    user_id = request.session.get('pending_user_id')
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            _send_login_otp(user)
            messages.success(request, 'A new code has been sent.')
        except User.DoesNotExist:
            pass
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been signed out.')
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset – Request
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetRequestView(View):
    template_name = 'accounts/forgot-password.html'

    def get(self, request):
        return render(request, self.template_name, {'form': PasswordResetRequestForm(), 'step': 1})

    def post(self, request):
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email, is_active=True)
                token_obj = PasswordResetToken.objects.create(user=user)
                _send_password_reset_email(request, user, token_obj)
            except User.DoesNotExist:
                pass  # Silently ignore – shown same success message
            messages.success(request, 'If that email exists, a reset link has been sent.')
            return redirect('accounts:forgot-password')
        return render(request, self.template_name, {'form': form, 'step': 1})


# ─────────────────────────────────────────────────────────────────────────────
# Password Reset – Confirm
# ─────────────────────────────────────────────────────────────────────────────
class PasswordResetConfirmView(View):
    template_name = 'accounts/forgot-password.html'

    def get(self, request, token):
        token_obj = get_object_or_404(PasswordResetToken, token=token, used=False)
        if not token_obj.is_valid():
            return render(request, self.template_name, {'expired': True})
        form = SetNewPasswordForm()
        return render(request, self.template_name, {'form': form, 'step': 3, 'token': token})

    def post(self, request, token):
        token_obj = get_object_or_404(PasswordResetToken, token=token, used=False)
        if not token_obj.is_valid():
            return render(request, self.template_name, {'expired': True})

        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            user = token_obj.user
            user.set_password(form.cleaned_data['password1'])
            user.save()
            token_obj.used = True
            token_obj.save()
            return render(request, self.template_name, {'step': 4, 'success': True})

        return render(request, self.template_name, {'form': form, 'step': 3, 'token': token})



