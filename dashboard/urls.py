"""dashboard/urls.py"""
from django.urls import path
from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('',                    views.home,              name='home'),
    path('settings/',           views.account_settings,  name='account_settings'),
    path('profit/',             views.profit_record,     name='profit_record'),
    path('transactions/',       views.transaction_history, name='transaction_history'),
    path('invest/',             views.invest,            name='invest'),
    path('invest/<str:investment_id>/deposit/', views.deposit_instructions, name='deposit_instructions'),
    path('account/delete/',                      views.delete_account,       name='delete_account'),
    path('withdraw/',           views.withdraw,          name='withdraw'),
    path('refer/',              views.refer_users,       name='refer_users'),
    path('support/',            views.help_support,      name='help_support'),
    path('exchange/',           views.crypto_exchange,   name='crypto_exchange'),
]
