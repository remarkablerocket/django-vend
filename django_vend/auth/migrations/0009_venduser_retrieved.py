# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-29 12:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('vend_auth', '0008_remove_venduser_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='venduser',
            name='retrieved',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
