# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-18 13:24
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0002_auto_20160518_1517'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='document',
            options={'ordering': ['-date_published']},
        ),
        migrations.RenameField(
            model_name='document',
            old_name='source_page_url',
            new_name='document_url',
        ),
    ]
