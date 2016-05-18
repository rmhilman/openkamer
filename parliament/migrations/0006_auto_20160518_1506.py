# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-18 13:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parliament', '0005_politicalparty_official_website_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partymember',
            name='person',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partymember', to='person.Person'),
        ),
    ]
