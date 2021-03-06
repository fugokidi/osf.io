# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-12-06 15:44
from __future__ import unicode_literals

from bulk_update.helper import bulk_update
from django.contrib.contenttypes.models import ContentType
from django.db import migrations
import progressbar


def noop(*args, **kwargs):
    # No brakes on the NPD train
    pass

def rekey_pagecounters(state, schema):
    AbstractNode = state.get_model('osf', 'AbstractNode')
    Guid = state.get_model('osf', 'Guid')
    Preprint = state.get_model('osf', 'Preprint')
    PageCounter = state.get_model('osf', 'PageCounter')
    nct = ContentType.objects.get_for_model(AbstractNode).id
    pct = ContentType.objects.get_for_model(Preprint).id

    preprints = Preprint.objects.select_related('node').exclude(primary_file_id__isnull=True).exclude(node_id__isnull=True)
    progress_bar = progressbar.ProgressBar(maxval=preprints.count() or 1).start()
    batch = []
    for i, preprint in enumerate(preprints, 1):
        node_id = Guid.objects.get(content_type=nct, object_id=preprint.node_id)._id
        file_id = preprint.primary_file._id
        if node_id and file_id:
            preprint_id = Guid.objects.filter(content_type=pct, object_id=preprint.id).values_list('_id', flat=True).first()
            if not preprint_id:
                assert False
            for page_counter in PageCounter.objects.filter(_id__startswith='download:{}:{}'.format(node_id, file_id)):
                page_counter._id = page_counter._id.replace(node_id, preprint_id)
                batch.append(page_counter)
        progress_bar.update(i)
    bulk_update(batch, update_fields=['_id'], batch_size=10000)
    progress_bar.finish()

class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0146_merge_20181119_2236'),
    ]

    operations = [
        migrations.RunPython(rekey_pagecounters, noop)
    ]
