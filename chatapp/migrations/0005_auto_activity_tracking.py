# Generated migration for auto-delete activity tracking

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('chatapp', '0004_anonymoususer_alter_userstatus_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='last_activity',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name='group',
            index=models.Index(fields=['last_activity'], name='chatapp_group_last_activity_idx'),
        ),
        migrations.AddIndex(
            model_name='group',
            index=models.Index(fields=['created_at'], name='chatapp_group_created_at_idx'),
        ),
        migrations.AlterModelOptions(
            name='group',
            options={'ordering': ['-last_activity']},
        ),
    ]
