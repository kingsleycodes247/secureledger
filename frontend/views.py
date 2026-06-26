from urllib import request

from django.shortcuts import render


def home(request):
    return render(request, 'frontend/home.html')

def about(request):
    return render(request, 'frontend/about.html')

def services(request):
    return render(request, 'frontend/services.html')

def contact(request):
    return render(request, 'frontend/contact.html')

'''
def register(request):
    return render(request, 'frontend/register.html')

def forgot_password(request):
    return render(request, 'frontend/forgot-password.html')

def login(request):
    return render(request, 'frontend/login.html')

def verify_email_view(request):
    return render(request,"frontend/verify-email.html")
'''
