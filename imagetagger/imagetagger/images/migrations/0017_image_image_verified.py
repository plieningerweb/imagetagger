# Generated by Django 2.0.9 on 2018-11-08 15:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0016_settag_test'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='image_verified',
            field=models.IntegerField(default=0),
        ),
    ]