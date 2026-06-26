from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    # Registration
    path('register/',                       views.RegisterView.as_view(),           name='register'),
    path('registration-pending/',           views.registration_pending,             name='registration_pending'),
    path('resend-verification/',            views.resend_verification,              name='resend_verification'),

    # Email verification
    path('verify-email/<uuid:token>/',      views.verify_email,                     name='verify_email'),

    # Login / logout
    path('login/',                          views.LoginView.as_view(),              name='login'),
    path('logout/',                         views.logout_view,                      name='logout'),

    # Login OTP verification
    path('verify-login-otp/', views.verify_login_otp, name='verify_login_otp'),
    path('resend-login-otp/', views.resend_login_otp, name='resend_login_otp'),

    # Password reset
    path('forgot-password/',                views.PasswordResetRequestView.as_view(), name='forgot-password'),
    path('reset-password/<uuid:token>/',    views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
