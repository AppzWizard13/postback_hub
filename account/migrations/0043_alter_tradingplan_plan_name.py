# Generated by Django 5.1.2 on 2024-12-01 05:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0042_dailygoalreport_plan_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tradingplan',
            name='plan_name',
            field=models.CharField(max_length=255),
        ),
    ]
