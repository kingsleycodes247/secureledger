from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, EmailVerificationToken, PasswordResetToken, SupportTicket

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ['email','first_name','last_name','is_email_verified','date_joined']
    list_filter   = ['is_email_verified','is_active','is_staff']
    search_fields = ['email','first_name','last_name','username']
    ordering      = ['-date_joined']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('SecureLedger', {'fields': ('phone','country','is_email_verified','referral_code','referred_by')}),
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user','account_balance','total_deposit','total_withdrawal','total_profit']
    search_fields = ['user__email']
    readonly_fields = ['created_at','updated_at']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display  = ['ticket_id','user','subject','status','priority','created_at']
    list_filter   = ['status','priority']
    search_fields = ['ticket_id','subject','user__email']
    readonly_fields = ['ticket_id','created_at']

admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)
