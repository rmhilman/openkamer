# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-15 18:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('forename', models.CharField(max_length=200)),
                ('surname', models.CharField(max_length=200)),
                ('surname_prefix', models.CharField(blank=True, default='', max_length=200)),
                ('birthdate', models.DateField(blank=True, null=True)),
                ('wikidata_id', models.CharField(blank=True, max_length=200)),
                ('wikimedia_image_name', models.CharField(blank=True, max_length=200)),
                ('wikimedia_image_url', models.URLField(blank=True)),
            ],
        ),
    ]
