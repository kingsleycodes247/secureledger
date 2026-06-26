from django.urls import path
from adminpanel import views

app_name = 'adminpanel'

urlpatterns = [
    path('',                                    views.admin_home,               name='home'),

    # Users
    path('users/',                              views.admin_users,              name='users'),
    path('users/<int:user_id>/',                views.admin_user_detail,        name='user_detail'),
    path('users/<int:user_id>/action/',         views.admin_user_action,        name='user_action'),

    # Transactions
    path('transactions/',                       views.admin_transactions,       name='transactions'),
    path('transactions/<int:tx_id>/action/',    views.admin_transaction_action, name='transaction_action'),

    # Investments
    path('investments/',                        views.admin_investments,        name='investments'),
    path('investments/<str:investment_id>/action/', views.admin_investment_action, name='investment_action'),

    path('wallets/<int:wallet_id>/delete/', views.admin_wallet_delete, name='wallet_delete'),

    # Plans
    path('plans/',                              views.admin_plans,              name='plans'),
    path('plans/<int:plan_id>/edit/',           views.admin_plan_edit,          name='plan_edit'),

    # Wallets
    path('wallets/',                            views.admin_wallets,            name='wallets'),

    # Support
    path('tickets/',                            views.admin_tickets,            name='tickets'),
    path('tickets/<int:ticket_id>/reply/',      views.admin_ticket_reply,       name='ticket_reply'),
]

