# Generated by Django 5.1.2 on 2024-10-20 16:21

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0002_control'),
    ]

    operations = [
        migrations.AddField(
            model_name='control',
            name='user',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='account.user'),
            preserve_default=False,
        ),
    ]
