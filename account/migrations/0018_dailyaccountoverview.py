# Generated by Django 5.1.2 on 2024-10-28 18:34

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0017_tempnotifiertable'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyAccountOverview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('opening_balance', models.FloatField()),
                ('deposit', models.FloatField()),
                ('withdrawal', models.FloatField()),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('pnl_status', models.FloatField()),
                ('expenses', models.FloatField()),
                ('closing_balance', models.FloatField()),
                ('order_count', models.IntegerField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_account_overviews', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
