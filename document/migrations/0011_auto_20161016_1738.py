# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-16 15:38
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0010_auto_20161015_1220'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kamerstuk',
            options={'ordering': ['document__date_published', 'id_sub'], 'verbose_name_plural': 'Kamerstukken'},
        ),
    ]
