# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-10 22:19
from __future__ import unicode_literals

from django.db import migrations
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission


def get_preprint_requests_perms():
    return Permission.objects.filter(codename__endswith='_preprintrequest').exclude(codename='add_preprintrequest')

def add_to_osf_admin_group_permissions(*args):

    # Add preprintrequests permissions to OSF Admin group
    admin_group = Group.objects.get(name='osf_admin')
    [admin_group.permissions.add(perm) for perm in get_preprint_requests_perms()]
    admin_group.save()

def remove_from_osf_admin_group_permissions(*args):

    # Remove preprintrequests permissions from OSF Admin group
    admin_group = Group.objects.get(name='osf_admin')
    [admin_group.permissions.remove(perm) for perm in get_preprint_requests_perms()]
    admin_group.save()


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0119_add_registrationprovider_perms_to_admin'),
    ]

    operations = [
        migrations.RunPython(add_to_osf_admin_group_permissions, remove_from_osf_admin_group_permissions),
    ]
