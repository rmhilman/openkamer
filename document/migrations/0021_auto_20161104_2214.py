# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-04 21:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0020_dossier_categories'),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(default='', max_length=250)),
            ],
            options={
                'abstract': False,
                'ordering': ['name'],
            },
        ),
        migrations.RenameModel(
            old_name='Category',
            new_name='DocumentCategory',
        ),
        migrations.AlterField(
            model_name='dossier',
            name='categories',
            field=models.ManyToManyField(blank=True, to='document.DossierCategory'),
        ),
    ]
