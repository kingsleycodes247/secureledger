from django.contrib import admin
from .models import InvestmentPlan, Investment, Transaction
from .models import CompanyWallet

@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ['name','label','daily_return_pct','duration_days','min_deposit','max_deposit','is_active']

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display  = ['investment_id','user','plan','amount','status','start_date','end_date']
    list_filter   = ['status','plan']
    search_fields = ['investment_id','user__email']
    readonly_fields = ['investment_id','expected_profit','expected_total']
    actions = ['activate_investments']

    def activate_investments(self, request, queryset):
        for inv in queryset.filter(status='pending'):
            inv.activate()
        self.message_user(request, f'{queryset.count()} investment(s) activated.')
    activate_investments.short_description = 'Activate selected investments'

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ['transaction_id','user','tx_type','amount','status','created_at']
    list_filter   = ['tx_type','status']
    search_fields = ['transaction_id','user__email']
    readonly_fields = ['transaction_id']
    actions = ['approve_transactions','reject_transactions']

    def approve_transactions(self, request, queryset):
        queryset.update(status='approved')
        from dashboard.views import _sync_profile
        for tx in queryset: _sync_profile(tx.user)
    approve_transactions.short_description = 'Approve selected transactions'

    def reject_transactions(self, request, queryset):
        queryset.update(status='rejected')
    reject_transactions.short_description = 'Reject selected transactions'


@admin.register(CompanyWallet)
class CompanyWalletAdmin(admin.ModelAdmin):
    list_display  = ['crypto', 'network', 'short_address', 'is_active']
    list_filter   = ['is_active', 'crypto']
    list_editable = ['is_active']
    search_fields = ['address', 'crypto']

    def short_address(self, obj):
        return f'{obj.address[:20]}…' if len(obj.address) > 20 else obj.address
    short_address.short_description = 'Address'