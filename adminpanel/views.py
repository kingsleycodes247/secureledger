from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.http import JsonResponse
from django.template.loader import render_to_string

from accounts.models import User, SupportTicket
from investments.models import InvestmentPlan, Investment, Transaction, CompanyWallet


# ─────────────────────────────────────────────────────────────────────────────
# Staff-only gate
# ─────────────────────────────────────────────────────────────────────────────
def staff_required(view_func):
    decorated = user_passes_test(
        lambda u: u.is_authenticated and u.is_staff,
        login_url='accounts:login',
    )(view_func)
    return decorated


# Helper: re-sync a user's profile totals after approving/rejecting money movements
def _sync_profile(user):
    from dashboard.views import _sync_profile as sync
    return sync(user)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD HOME — platform-wide stats
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_home(request):
    total_users        = User.objects.filter(is_staff=False).count()
    verified_users     = User.objects.filter(is_email_verified=True, is_staff=False).count()
    total_deposits     = Transaction.objects.filter(tx_type='deposit', status='approved').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_withdrawals  = Transaction.objects.filter(tx_type='withdrawal', status='approved').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    pending_deposits   = Transaction.objects.filter(tx_type='deposit', status='pending').count()
    pending_withdrawals= Transaction.objects.filter(tx_type='withdrawal', status='pending').count()
    active_investments = Investment.objects.filter(status='active').count()
    pending_investments= Investment.objects.filter(status='pending').count()
    open_tickets       = SupportTicket.objects.filter(status='open').count()

    # Recent activity
    recent_users        = User.objects.filter(is_staff=False).order_by('-date_joined')[:5]
    recent_transactions = Transaction.objects.select_related('user').order_by('-created_at')[:8]
    pending_proofs      = Investment.objects.filter(status='pending', proof_of_payment__isnull=False).select_related('user', 'plan').order_by('-proof_uploaded_at')[:5]

    context = {
        'total_users': total_users,
        'verified_users': verified_users,
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'net_balance': total_deposits - total_withdrawals,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'active_investments': active_investments,
        'pending_investments': pending_investments,
        'open_tickets': open_tickets,
        'recent_users': recent_users,
        'recent_transactions': recent_transactions,
        'pending_proofs': pending_proofs,
        'page': 'dashboard',
    }
    return render(request, 'adminpanel/home.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_users(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', 'all')

    users = User.objects.filter(is_staff=False).select_related('profile').order_by('-date_joined')
    if q:
        users = users.filter(Q(email__icontains=q) | Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if status == 'verified':
        users = users.filter(is_email_verified=True)
    elif status == 'unverified':
        users = users.filter(is_email_verified=False)
    elif status == 'active':
        users = users.filter(is_active=True)
    elif status == 'suspended':
        users = users.filter(is_active=False)

    return render(request, 'adminpanel/users.html', {
        'users': users, 'q': q, 'status_filter': status, 'page': 'users',
    })


@staff_required
def admin_user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    investments = user.investments.select_related('plan').order_by('-created_at')
    transactions = user.transactions.order_by('-created_at')
    return render(request, 'adminpanel/user_detail.html', {
        'target_user': user, 'investments': investments, 'transactions': transactions, 'page': 'users',
    })


@staff_required
@require_POST
def admin_user_action(request, user_id):
    user = get_object_or_404(User, id=user_id)
    action = request.POST.get('action')

    if action == 'suspend':
        user.is_active = False; user.save()
        messages.success(request, f'{user.email} has been suspended.')
    elif action == 'activate':
        user.is_active = True; user.save()
        messages.success(request, f'{user.email} has been re-activated.')
    elif action == 'verify':
        user.is_email_verified = True; user.save()
        messages.success(request, f'{user.email} has been manually verified.')
    elif action == 'credit':
        amount = Decimal(request.POST.get('amount', '0') or '0')
        tx_type = request.POST.get('tx_type', 'bonus')
        if amount > 0:
            Transaction.objects.create(user=user, tx_type=tx_type, amount=amount, status='approved', note=f'Admin {tx_type} credit')
            _sync_profile(user)
            messages.success(request, f'${amount} {tx_type} credited to {user.email}.')
    elif action == 'delete':
        email = user.email
        user.delete()
        messages.success(request, f'{email} has been permanently deleted.')
        return redirect('adminpanel:users')

    return redirect('adminpanel:user_detail', user_id=user.id)


# ─────────────────────────────────────────────────────────────────────────────
# DEPOSITS / TRANSACTIONS — approve / reject
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_transactions(request):
    tx_type = request.GET.get('type', 'all')
    status = request.GET.get('status', 'all')

    txs = Transaction.objects.select_related('user', 'investment__plan').order_by('-created_at')
    if tx_type != 'all':
        txs = txs.filter(tx_type=tx_type)
    if status != 'all':
        txs = txs.filter(status=status)

    return render(request, 'adminpanel/transactions.html', {
        'transactions': txs, 'tx_type': tx_type, 'status_filter': status, 'page': 'transactions',
    })


@staff_required
@require_POST
def admin_transaction_action(request, tx_id):
    tx = get_object_or_404(Transaction, id=tx_id)
    action = request.POST.get('action')

    if action == 'approve':
        tx.status = 'approved'; tx.save()
        # If a deposit tied to an investment → activate the plan
        if tx.tx_type == 'deposit' and tx.investment and tx.investment.status == 'pending':
            tx.investment.activate()
        _sync_profile(tx.user)
        messages.success(request, f'Transaction {tx.transaction_id} approved.')
    elif action == 'reject':
        tx.status = 'rejected'; tx.save()
        if tx.investment and tx.investment.status == 'pending':
            tx.investment.status = 'cancelled'; tx.investment.save()
        _sync_profile(tx.user)
        messages.success(request, f'Transaction {tx.transaction_id} rejected.')

    return redirect(request.META.get('HTTP_REFERER', 'adminpanel:transactions'))


# ─────────────────────────────────────────────────────────────────────────────
# INVESTMENTS — review proof, approve / reject
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_investments(request):
    status = request.GET.get('status', 'all')
    invs = Investment.objects.select_related('user', 'plan').order_by('-created_at')
    if status != 'all':
        invs = invs.filter(status=status)
    return render(request, 'adminpanel/investments.html', {
        'investments': invs, 'status_filter': status, 'page': 'investments',
    })



@staff_required
@require_POST
def admin_investment_action(request, investment_id):
    inv = get_object_or_404(Investment, investment_id=investment_id)
    action = request.POST.get('action')

    if action == 'approve':
        inv.activate()
        Transaction.objects.filter(
            investment=inv, tx_type='deposit', status='pending'
        ).update(status='approved')
        _sync_profile(inv.user)

        # Branded approval email
        try:
            dashboard_url = request.build_absolute_uri('/dashboard/')
            html_body = render_to_string('emails/investment_approved.html', {
                'user': inv.user,
                'investment': inv,
                'dashboard_url': dashboard_url,
            })
            send_mail(
                subject='Your SecureLedger investment is now active ✅',
                message=(
                    f'Hi {inv.user.first_name}, your {inv.plan.get_name_display()} '
                    f'(${inv.amount}) is now active. Expected profit: ${inv.expected_profit}.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[inv.user.email],
                html_message=html_body,
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, f'Investment {inv.investment_id} approved & activated.')

    elif action == 'reject':
        inv.status = 'cancelled'
        inv.save()
        Transaction.objects.filter(
            investment=inv, tx_type='deposit', status='pending'
        ).update(status='rejected')

        # Branded rejection email
        try:
            support_url = request.build_absolute_uri('/dashboard/support/')
            html_body = render_to_string('emails/investment_rejected.html', {
                'user': inv.user,
                'investment': inv,
                'support_url': support_url,
            })
            send_mail(
                subject='Action needed: your SecureLedger deposit',
                message=(
                    f'Hi {inv.user.first_name}, we could not verify the payment for '
                    f'your {inv.plan.get_name_display()} investment ({inv.investment_id}). '
                    f'Please contact support.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[inv.user.email],
                html_message=html_body,
                fail_silently=True,
            )
        except Exception:
            pass

        messages.success(request, f'Investment {inv.investment_id} rejected.')

    return redirect(request.META.get('HTTP_REFERER', 'adminpanel:investments'))


# ─────────────────────────────────────────────────────────────────────────────
# PLANS — CRUD
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_plans(request):
    plans = InvestmentPlan.objects.all().order_by('min_deposit')
    return render(request, 'adminpanel/plans.html', {'plans': plans, 'page': 'plans'})


@staff_required
@require_POST
def admin_plan_edit(request, plan_id):
    plan = get_object_or_404(InvestmentPlan, id=plan_id)
    plan.daily_return_pct = Decimal(request.POST.get('daily_return_pct', plan.daily_return_pct))
    plan.duration_days = int(request.POST.get('duration_days', plan.duration_days))
    plan.min_deposit = Decimal(request.POST.get('min_deposit', plan.min_deposit))
    plan.max_deposit = Decimal(request.POST.get('max_deposit', plan.max_deposit))
    plan.referral_bonus_pct = Decimal(request.POST.get('referral_bonus_pct', plan.referral_bonus_pct))
    plan.is_active = request.POST.get('is_active') == 'on'
    plan.save()
    messages.success(request, f'{plan.get_name_display()} updated.')
    return redirect('adminpanel:plans')


# ─────────────────────────────────────────────────────────────────────────────
# WALLETS — manage company deposit addresses
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_wallets(request):
    wallets = CompanyWallet.objects.all()

    if request.method == 'POST':
        wallet_id = request.POST.get('wallet_id')   # present when EDITING
        crypto    = request.POST.get('crypto')

        if wallet_id:
            wallet = get_object_or_404(CompanyWallet, id=wallet_id)
        else:
            # New wallet — block duplicate crypto
            if CompanyWallet.objects.filter(crypto=crypto).exists():
                messages.error(request, f'A {crypto} wallet already exists. Edit it instead.')
                return redirect('adminpanel:wallets')
            wallet = CompanyWallet(crypto=crypto)

        wallet.network = request.POST.get('network', '')
        wallet.address = request.POST.get('address', '')
        wallet.is_active = request.POST.get('is_active') == 'on'
        if request.FILES.get('qr_code'):
            wallet.qr_code = request.FILES['qr_code']
        wallet.save()
        messages.success(request, f'{wallet.get_crypto_display()} wallet saved.')
        return redirect('adminpanel:wallets')

    return render(request, 'adminpanel/wallets.html', {'wallets': wallets, 'page': 'wallets'})


@staff_required
@require_POST
def admin_wallet_delete(request, wallet_id):
    wallet = get_object_or_404(CompanyWallet, id=wallet_id)
    name = wallet.get_crypto_display()
    wallet.delete()
    messages.success(request, f'{name} wallet deleted.')
    return redirect('adminpanel:wallets')

# ─────────────────────────────────────────────────────────────────────────────
# SUPPORT TICKETS
# ─────────────────────────────────────────────────────────────────────────────
@staff_required
def admin_tickets(request):
    status = request.GET.get('status', 'all')
    tickets = SupportTicket.objects.select_related('user').order_by('-created_at')
    if status != 'all':
        tickets = tickets.filter(status=status)
    return render(request, 'adminpanel/tickets.html', {'tickets': tickets, 'status_filter': status, 'page': 'tickets'})


@staff_required
@require_POST
def admin_ticket_reply(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    reply = request.POST.get('admin_reply', '').strip()
    new_status = request.POST.get('status', ticket.status)
    if reply:
        ticket.admin_reply = reply
    ticket.status = new_status
    ticket.save()
    try:
        send_mail(
            f'Re: Your SecureLedger ticket #{ticket.ticket_id}',
            f'Hi {ticket.user.first_name},\n\n{reply}\n\n— SecureLedger Support',
            settings.DEFAULT_FROM_EMAIL, [ticket.user.email], fail_silently=True,
        )
    except Exception:
        pass
    messages.success(request, f'Reply sent for ticket #{ticket.ticket_id}.')
    return redirect('adminpanel:tickets')
