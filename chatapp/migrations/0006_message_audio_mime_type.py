# Generated migration for audio MIME type field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chatapp', '0005_auto_activity_tracking'),
    ]

    operations = [
        # Add audio_mime_type field with default value
        migrations.AddField(
            model_name='message',
            name='audio_mime_type',
            field=models.CharField(
                default='audio/webm',
                help_text='MIME type of audio file',
                max_length=50
            ),
        ),
    ]
