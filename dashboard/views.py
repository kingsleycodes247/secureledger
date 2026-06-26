from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Sum
from django.utils import timezone

from accounts.models import SupportTicket, UserProfile
from accounts.forms import ProfileUpdateForm, PasswordUpdateForm, SupportTicketForm
from investments.models import InvestmentPlan, Investment, Transaction, CompanyWallet
from investments.forms import InvestForm, WithdrawalForm, ProofOfPaymentForm
 
from django.contrib.auth import logout


# ─────────────────────────────────────────────────────────────────────────────
# Helper – recalculate and sync profile financial totals
# ─────────────────────────────────────────────────────────────────────────────
def _sync_profile(user):
    """Re-compute all financial summary fields on UserProfile."""
    p = user.profile

    approved_tx = user.transactions.filter(status='approved')

    p.total_deposit = approved_tx.filter(
        tx_type='deposit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    p.total_withdrawal = approved_tx.filter(
        tx_type='withdrawal'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    p.total_profit = approved_tx.filter(
        tx_type='profit'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    p.total_bonus = approved_tx.filter(
        tx_type='bonus'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    p.total_referral_bonus = approved_tx.filter(
        tx_type='referral_bonus'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    p.account_balance = (
        p.total_deposit
        + p.total_profit
        + p.total_bonus
        + p.total_referral_bonus
        - p.total_withdrawal
    )
    p.save()
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Home
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def home(request):
    profile = _sync_profile(request.user)
    active_investments = request.user.investments.filter(status='active').select_related('plan')
    recent_transactions = request.user.transactions.select_related('investment__plan')[:5]

    # Time-of-day greeting
    hour = timezone.localtime().hour
    greeting = 'Good Morning' if hour < 12 else ('Good Afternoon' if hour < 17 else 'Good Evening')

    context = {
        'profile': profile,
        'active_investments': active_investments,
        'recent_transactions': recent_transactions,
        'greeting': greeting,
        'total_plans': request.user.investments.count(),
        'active_plans_count': active_investments.count(),
        'page': 'dashboard',
    }
    return render(request, 'dashboard/home.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Account Settings
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def account_settings(request):
    profile = request.user.profile
    profile_form = ProfileUpdateForm(instance=profile, initial={
        'first_name': request.user.first_name,
        'last_name':  request.user.last_name,
        'phone':      request.user.phone,
        'country':    request.user.country,
    })
    password_form = PasswordUpdateForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                # Update User fields
                request.user.first_name = profile_form.cleaned_data['first_name']
                request.user.last_name  = profile_form.cleaned_data['last_name']
                request.user.phone      = profile_form.cleaned_data['phone']
                request.user.country    = profile_form.cleaned_data['country']
                request.user.save()
                profile_form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('dashboard:account_settings')

        elif action == 'change_password':
            password_form = PasswordUpdateForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('dashboard:account_settings')

    return render(request, 'dashboard/account_settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': profile,
        'page': 'account_settings',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Profit Record
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def profit_record(request):
    profits = request.user.transactions.filter(
        tx_type__in=['profit', 'bonus', 'referral_bonus']
    ).select_related('investment__plan').order_by('-created_at')

    total_profit = profits.filter(tx_type='profit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_bonus  = profits.filter(tx_type='bonus').aggregate(t=Sum('amount'))['t'] or Decimal('0')
    total_ref    = profits.filter(tx_type='referral_bonus').aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return render(request, 'dashboard/profit_record.html', {
        'profits': profits,
        'total_profit': total_profit,
        'total_bonus': total_bonus,
        'total_referral_bonus': total_ref,
        'grand_total': total_profit + total_bonus + total_ref,
        'page': 'profit_record',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Transaction History
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def transaction_history(request):
    tx_type = request.GET.get('type', 'all')
    status  = request.GET.get('status', 'all')

    txs = request.user.transactions.select_related('investment__plan').order_by('-created_at')

    if tx_type != 'all':
        txs = txs.filter(tx_type=tx_type)
    if status != 'all':
        txs = txs.filter(status=status)

    return render(request, 'dashboard/transaction_history.html', {
        'transactions': txs,
        'tx_type': tx_type,
        'status_filter': status,
        'page': 'transactions',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Invest – Plan List + Subscription
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def invest(request):
    plans = InvestmentPlan.objects.filter(is_active=True)
    my_investments = request.user.investments.select_related('plan').order_by('-created_at')
    form = InvestForm(request.user)
 
    if request.method == 'POST':
        form = InvestForm(request.user, request.POST)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.user = request.user
            inv.status = 'pending'
            inv.save()
 
            # Create the pending deposit transaction
            Transaction.objects.create(
                user=request.user,
                tx_type='deposit',
                amount=inv.amount,
                payment_method=inv.payment_method,
                status='pending',
                investment=inv,
                note=f'Deposit for {inv.plan.get_name_display()}',
            )
 
            messages.success(request, 'Investment created! Complete your deposit below to activate it.')
            # → go to the deposit instructions / proof upload page
            return redirect('dashboard:deposit_instructions', investment_id=inv.investment_id)
 
    return render(request, 'dashboard/invest.html', {
        'plans': plans,
        'my_investments': my_investments,
        'form': form,
        'profile': request.user.profile,
        'page': 'invest',
    })
 
 
# ─────────────────────────────────────────────────────────────────────────────
# INVEST — Step 2: show company wallet + accept proof-of-payment upload
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def deposit_instructions(request, investment_id):
    investment = get_object_or_404(
        Investment, investment_id=investment_id, user=request.user
    )
 
    # Find the company wallet matching the chosen crypto
    wallet = CompanyWallet.objects.filter(
        crypto=investment.payment_method, is_active=True
    ).first()
 
    proof_form = ProofOfPaymentForm(instance=investment)
 
    if request.method == 'POST':
        proof_form = ProofOfPaymentForm(request.POST, request.FILES, instance=investment)
        if proof_form.is_valid():
            inv = proof_form.save(commit=False)
            inv.proof_uploaded_at = timezone.now()
            inv.save()
            messages.success(
                request,
                'Proof of payment uploaded! Our team will verify and activate your plan shortly.'
            )
            return redirect('dashboard:invest')
        else:
            messages.error(request, 'Please upload a valid image file (screenshot).')
 
    return render(request, 'dashboard/deposit_instructions.html', {
        'investment': investment,
        'wallet': wallet,
        'proof_form': proof_form,
        'page': 'invest',
    })
 
 
# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT DELETION
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_account(request):
    """
    Permanently delete the logged-in user's account.
    Requires password confirmation for safety.
    """
    password = request.POST.get('confirm_password', '')
    confirm_text = request.POST.get('confirm_text', '').strip().upper()
 
    # Safety checks
    if confirm_text != 'DELETE':
        messages.error(request, 'You must type DELETE to confirm account deletion.')
        return redirect('dashboard:account_settings')
 
    if not request.user.check_password(password):
        messages.error(request, 'Incorrect password. Account was not deleted.')
        return redirect('dashboard:account_settings')
 
    # Block deletion if the user has active investments (optional safety)
    if request.user.investments.filter(status='active').exists():
        messages.error(
            request,
            'You have active investment plans. Please wait until they mature before deleting your account.'
        )
        return redirect('dashboard:account_settings')
 
    user = request.user
    logout(request)
    user.delete()   # cascades to profile, investments, transactions, tickets
 
    messages.success(request, 'Your account has been permanently deleted. We\'re sorry to see you go.')
    return redirect('frontend:home')

# ─────────────────────────────────────────────────────────────────────────────
# Withdrawal
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def withdraw(request):
    profile = _sync_profile(request.user)
    # Validate against AVAILABLE (withdrawable) balance, NOT total balance
    form = WithdrawalForm(profile.available_balance)

    if request.method == 'POST':
        form = WithdrawalForm(profile.available_balance, request.POST)
        if form.is_valid():
            Transaction.objects.create(
                user=request.user,
                tx_type='withdrawal',
                amount=form.cleaned_data['amount'],
                payment_method=form.cleaned_data['payment_method'],
                wallet_address=form.cleaned_data['wallet_address'],
                status='pending',
                note='Withdrawal request',
            )
            messages.success(request, 'Withdrawal request submitted. Processing within 24 hours.')
            return redirect('dashboard:transaction_history')

    return render(request, 'dashboard/withdraw.html', {
        'form': form,
        'profile': profile,
        'page': 'transactions',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Refer Users
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def refer_users(request):
    referrals = request.user.referrals.select_related('profile').order_by('-date_joined')
    referral_earnings = request.user.transactions.filter(
        tx_type='referral_bonus', status='approved'
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    referral_url = request.build_absolute_uri(
        f'/auth/register/?ref={request.user.referral_code}'
    )

    return render(request, 'dashboard/refer_users.html', {
        'referrals': referrals,
        'referral_count': referrals.count(),
        'referral_earnings': referral_earnings,
        'referral_url': referral_url,
        'referral_code': request.user.referral_code,
        'page': 'refer',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Help / Support
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def help_support(request):
    tickets = request.user.tickets.order_by('-created_at')
    form = SupportTicketForm()

    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            SupportTicket.objects.create(
                user=request.user,
                subject=dict(form.fields['subject'].choices).get(
                    form.cleaned_data['subject'], form.cleaned_data['subject']
                ),
                priority=form.cleaned_data['priority'],
                message=form.cleaned_data['message'],
            )
            messages.success(request, 'Support ticket submitted. We\'ll respond within 24 hours.')
            return redirect('dashboard:help_support')

    return render(request, 'dashboard/help_support.html', {
        'tickets': tickets,
        'form': form,
        'open_count': tickets.filter(status='open').count(),
        'page': 'support',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Crypto Exchange (placeholder – embed or link to exchange partner)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def crypto_exchange(request):
    return render(request, 'dashboard/crypto_exchange.html', {
        'page': 'exchange',
        'profile': request.user.profile,
    })
