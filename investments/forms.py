"""investments/forms.py"""
from decimal import Decimal
from django import forms
from .models import InvestmentPlan, Investment

PAYMENT_METHODS = [
    ('', 'Select payment method'),
    ('BTC',  'Bitcoin (BTC)'),
    ('USDT', 'Tether USDT (TRC20)'),
    ('ETH',  'Ethereum (ETH)'),
    ('SOL',  'Solana (SOL)'),
]


class InvestForm(forms.ModelForm):
    plan           = forms.ModelChoiceField(queryset=InvestmentPlan.objects.filter(is_active=True), widget=forms.Select(attrs={'class': 'form-input', 'id': 'investPlan'}))
    amount         = forms.DecimalField(max_digits=18, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Enter amount in USD', 'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=PAYMENT_METHODS, widget=forms.Select(attrs={'class': 'form-input'}))

    class Meta:
        model  = Investment
        fields = ['plan', 'amount', 'payment_method']

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        plan   = cleaned.get('plan')
        amount = cleaned.get('amount')
        if plan and amount:
            if amount < plan.min_deposit:
                raise forms.ValidationError(f'Minimum deposit for {plan.get_name_display()} is ${plan.min_deposit:,.2f}')
            if amount > plan.max_deposit:
                raise forms.ValidationError(f'Maximum deposit for {plan.get_name_display()} is ${plan.max_deposit:,.2f}')
        return cleaned

    def save(self, commit=True):
        inv = super().save(commit=False)
        inv.expected_profit = inv.plan.expected_profit(inv.amount)
        inv.expected_total  = inv.plan.expected_total(inv.amount)
        if commit:
            inv.save()
        return inv


class WithdrawalForm(forms.Form):
    amount         = forms.DecimalField(max_digits=18, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Amount to withdraw', 'step': '0.01'}))
    wallet_address = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-input font-mono', 'placeholder': 'Your crypto wallet address'}))
    payment_method = forms.ChoiceField(choices=PAYMENT_METHODS[1:], widget=forms.Select(attrs={'class': 'form-input'}))

    def __init__(self, available_balance=Decimal('0'), *args, **kwargs):
        self.available_balance = available_balance
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Enter a positive amount.')
        if amount > self.available_balance:
            raise forms.ValidationError(
                f'Insufficient withdrawable balance. '
                f'Available: ${self.available_balance:,.2f} '
                f'(invested capital is locked until your plans mature).'
            )
        return amount


class ProofOfPaymentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = ['proof_of_payment']
        widgets = {'proof_of_payment': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-input'})}
