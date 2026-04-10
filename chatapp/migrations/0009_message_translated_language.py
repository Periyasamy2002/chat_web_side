# Generated migration for multi-language support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatapp', '0008_message_translated_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='translated_language',
            field=models.CharField(
                blank=True, 
                default='', 
                help_text='Language that translated_content is in', 
                max_length=50
            ),
        ),
    ]
