from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0025_add_purchase'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prospect',
            name='stage',
            field=models.CharField(
                choices=[
                    ('Rascunho', 'Rascunho'),
                    ('Prospeccao', 'Prospecção'),
                    ('Aguardando retorno', 'Aguardando retorno'),
                    ('Follow-up', 'Follow-up'),
                    ('Negociacao', 'Negociação'),
                    ('Fechado', 'Fechado'),
                ],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='prospect',
            name='archive_reason',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Ativo'),
                    ('sem_retorno', 'Sem retorno'),
                    ('nao_tem_interesse', 'Não tem interesse'),
                    ('pausado', 'Pausado'),
                    ('fechado', 'Fechado'),
                ],
                default='',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='prospect',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='prospect',
            name='last_activity_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='prospect',
            name='channel',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
    ]
