from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='agegroup',
            index=models.Index(fields=['min_age', 'max_age', 'gender'], name='accounts_ag_min_age_idx'),
        ),
        migrations.AddIndex(
            model_name='participant',
            index=models.Index(fields=['age_group', 'name'], name='accounts_pa_age_grp_idx'),
        ),
        migrations.AddIndex(
            model_name='participant',
            index=models.Index(fields=['username'], name='accounts_pa_usernam_idx'),
        ),
        migrations.AddIndex(
            model_name='boulder',
            index=models.Index(fields=['label'], name='accounts_bo_label_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['participant', '-updated_at'], name='accounts_re_part_upd_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['boulder', '-updated_at'], name='accounts_re_bould_upd_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['participant', 'boulder'], name='accounts_re_part_bou_idx'),
        ),
    ]
