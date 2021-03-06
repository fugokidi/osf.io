# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-11-08 16:56
from __future__ import unicode_literals

from django.db import migrations
from osf.models import Collection
from django.contrib.contenttypes.models import ContentType


def reverse_func(state, schema):
    preprint_content_type = ContentType.objects.get(app_label='osf', model='preprint')
    ThroughModel = Collection.collected_types.through
    ThroughModel.objects.filter(contenttype_id=preprint_content_type.id).delete()


def add_preprint_type_to_collections(state, schema):
    ThroughModel = Collection.collected_types.through
    preprint_ct_id = ContentType.objects.get(app_label='osf', model='preprint').id

    through_objects = []
    collections = Collection.objects.exclude(collected_types__in=[preprint_ct_id])
    for collection in collections:
        through_objects.append(ThroughModel(collection_id=collection.id, contenttype_id=preprint_ct_id))

    ThroughModel.objects.bulk_create(through_objects)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0144_merge_20181113_1420'),
    ]

    operations = [
        migrations.RunPython(add_preprint_type_to_collections, reverse_func)
    ]
