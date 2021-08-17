# Generated by Django 2.2.24 on 2021-08-20 19:18

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_goals', '0006_auto_20210820_1917'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coursegoal',
            name='unsubscribe_token',
            field=models.UUIDField(blank=True, default=uuid.uuid4, editable=False, help_text='Used to validate unsubscribe requests without requiring a login', null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalcoursegoal',
            name='unsubscribe_token',
            field=models.UUIDField(blank=True, db_index=True, default=uuid.uuid4, editable=False, help_text='Used to validate unsubscribe requests without requiring a login', null=True),
        ),
    ]
