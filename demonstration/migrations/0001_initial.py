# Generated by Django 4.1.2 on 2022-10-11 17:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ModelA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_a', models.TextField()),
                ('count_a', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='ModelB',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_b', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='HasRelations',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ref_a', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='demonstration.modela')),
                ('ref_b', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='demonstration.modelb')),
            ],
        ),
        migrations.CreateModel(
            name='ChildrenOfA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='children', to='demonstration.modela')),
            ],
        ),
    ]