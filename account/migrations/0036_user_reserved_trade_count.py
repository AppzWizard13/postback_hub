# Generated by Django 5.1.2 on 2024-11-25 13:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0035_dailyselfanalysis_overall_advice'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='reserved_trade_count',
            field=models.IntegerField(default=0),
        ),
    ]
