# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-29 09:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('government', '0003_auto_20161024_1356'),
    ]

    operations = [
        migrations.AddField(
            model_name='government',
            name='slug',
            field=models.SlugField(default='', max_length=250),
        ),
    ]
