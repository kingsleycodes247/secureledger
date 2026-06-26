from django.db import migrations
from decimal import Decimal

PLANS = [
    dict(name='bronze', label='3.2% DAILY FOR 7 DAYS',  daily_return_pct=Decimal('3.2'),  duration_days=7,  min_deposit=Decimal('100'),   max_deposit=Decimal('999')),
    dict(name='silver', label='4.8% DAILY FOR 8 DAYS',  daily_return_pct=Decimal('4.8'),  duration_days=8,  min_deposit=Decimal('1000'),  max_deposit=Decimal('5999')),
    dict(name='gold',   label='6.2% AFTER 10 DAYS',     daily_return_pct=Decimal('6.2'),  duration_days=10, min_deposit=Decimal('6000'),  max_deposit=Decimal('19000')),
    dict(name='diamond',label='7.3% DAILY FOR 12 DAYS', daily_return_pct=Decimal('7.3'),  duration_days=12, min_deposit=Decimal('20000'), max_deposit=Decimal('34999')),
    dict(name='mining', label='10% DAILY FOR 14 DAYS',  daily_return_pct=Decimal('10.0'), duration_days=14, min_deposit=Decimal('35000'), max_deposit=Decimal('500000')),
]

def seed_plans(apps, schema_editor):
    Plan = apps.get_model('investments', 'InvestmentPlan')
    for p in PLANS:
        Plan.objects.get_or_create(name=p['name'], defaults={**p, 'referral_bonus_pct': Decimal('10.00'), 'is_active': True})

class Migration(migrations.Migration):
    dependencies = [('investments', '0001_initial')]
    operations = [migrations.RunPython(seed_plans, migrations.RunPython.noop)]
