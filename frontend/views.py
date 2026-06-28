from urllib import request
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def home(request):
    return render(request, 'frontend/home.html')

def about(request):
    return render(request, 'frontend/about.html')

def services(request):
    return render(request, 'frontend/services.html')

def contact(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        subject    = request.POST.get('subject', '').strip()
        message    = request.POST.get('message', '').strip()

        # Basic validation
        if not (first_name and email and message):
            messages.error(request, 'Please fill in your name, email, and message.')
            return redirect('frontend:contact')

        full_name = f'{first_name} {last_name}'.strip()

        # ── 1. Notify the team (goes to the info mailbox) ──
        try:
            admin_html = render_to_string('emails/contact_admin.html', {
                'full_name': full_name,
                'email': email,
                'phone': phone,
                'subject': subject,
                'message': message,
            })
            admin_mail = EmailMultiAlternatives(
                subject=f'New Contact Message: {subject or "General Enquiry"}',
                body=(
                    f'From: {full_name} <{email}>\n'
                    f'Phone: {phone or "—"}\n'
                    f'Subject: {subject or "—"}\n\n{message}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.CONTACT_EMAIL],
                reply_to=[email],   # so you can reply straight to the visitor
            )
            admin_mail.attach_alternative(admin_html, 'text/html')
            admin_mail.send(fail_silently=False)
        except Exception as e:
            print(f'Contact admin email failed: {e}')
            messages.error(request, 'Something went wrong sending your message. Please try again.')
            return redirect('frontend:contact')

        # ── 2. Auto-reply / thank-you to the user ──
        try:
            user_html = render_to_string('emails/contact_thankyou.html', {
                'first_name': first_name,
                'subject': subject,
                'message': message,
            })
            send_mail(
                subject='Thank you for reaching out to SecureLedger',
                message=(
                    f'Hi {first_name},\n\n'
                    f'Thank you for reaching out to SecureLedger. We\'ve received your '
                    f'message and our team will get in touch with you shortly.\n\n'
                    f'— The SecureLedger Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=user_html,
                fail_silently=True,   # don't fail the whole request if the auto-reply bounces
            )
        except Exception as e:
            print(f'Contact thank-you email failed: {e}')

        messages.success(request, 'Thank you for reaching out! We\'ve received your message and will get in touch shortly.')
        return redirect('frontend:contact')

    return render(request, 'frontend/contact.html')

