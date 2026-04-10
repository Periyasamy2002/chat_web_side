# Generated migration for adding translation support to Message model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatapp', '0007_merge_20260408_1551'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='translated_content',
            field=models.TextField(blank=True, null=True, help_text='Cached translation of original content'),
        ),
    ]
