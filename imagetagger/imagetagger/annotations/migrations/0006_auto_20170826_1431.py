# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-26 12:31
from __future__ import unicode_literals

import json

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0005_auto_20170826_1424'),
    ]

    def forward_func(apps, schema_editor):
        Annotation = apps.get_model("annotations", "Annotation")
        db_alias = schema_editor.connection.alias

        # Copy all valid annotations from raw_vector to vector
        for annotation in Annotation.objects.using(db_alias).all():
            try:
                vector = json.loads(annotation.raw_vector)
                for key, value in vector.items():
                    try:
                        # try to convert all numeric vector values to integer
                        vector[key] = int(value)
                    except ValueError:
                        continue
                annotation.vector = vector
                annotation.save()
            except ValueError:
                # Annotation is invalid, delete it
                annotation.delete()

    def backward_func(apps, schema_editor):
        Annotation = apps.get_model("annotations", "Annotation")
        db_alias = schema_editor.connection.alias

        # Copy all annotations from vector to raw_vector
        for annotation in Annotation.objects.using(db_alias).all():
            annotation.raw_vector = json.dumps(annotation.vector)
            annotation.save()

    operations = [
        migrations.RenameField(
            model_name='annotation',
            old_name='vector',
            new_name='raw_vector',
        ),
        migrations.AddField(
            model_name='annotation',
            name='vector',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
        migrations.RunPython(forward_func, backward_func, atomic=True),
    ]
