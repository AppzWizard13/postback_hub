# Generated by Django 5.1.2 on 2024-11-11 22:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0028_rename_day_closing_dailyaccountoverview_day_close_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='control',
            name='stoploss_type',
            field=models.CharField(choices=[('percentage', 'Percentage'), ('points', 'Points')], default='percentage', max_length=10),
        ),
    ]