#!/usr/bin/env python
# encoding: utf-8

import os
import mock
from nose.tools import *  # noqa

from framework.auth.core import Auth
from website.addons.osfstorage.tests.utils import (
    StorageTestCase, Delta, AssertDeltas,
    recursively_create_file, recursively_create_folder
)
from website.addons.osfstorage.tests import factories

import furl

from framework.auth import signing
from website.util import rubeus

from website.addons.osfstorage import model
from website.addons.osfstorage import utils
from website.addons.osfstorage import views
from website.addons.base.views import make_auth
from website.addons.osfstorage import settings as storage_settings


def create_record_with_version(path, node_settings, **kwargs):
    version = factories.FileVersionFactory(**kwargs)
    node_settings.root_node.append_file(path)
    record.versions.append(version)
    record.save()
    return record


class HookTestCase(StorageTestCase):

    def send_hook(self, view_name, payload, method='get', **kwargs):
        method = getattr(self.app, method)
        return method(
            self.project.api_url_for(view_name),
            signing.sign_data(signing.default_signer, payload),
            **kwargs
        )


class TestGetMetadataHook(HookTestCase):

    def test_file_metata(self):
        path = u'kind/of/magíc.mp3'
        record = recursively_create_file(self.node_settings, path)
        version = factories.FileVersionFactory()
        record.versions.append(version)
        record.save()
        res = self.send_hook(
            'osf_storage_get_metadata_hook',
            {'path': record.parent._id},
        )
        assert_equal(len(res.json), 1)
        assert_equal(
            res.json[0],
            record.serialized()
        )

    def test_osf_storage_root(self):
        auth = Auth(self.project.creator)
        result = views.osf_storage_root(self.node_settings, auth=auth)
        node = self.project
        expected = rubeus.build_addon_root(
            node_settings=self.node_settings,
            name='',
            permissions=auth,
            user=auth.user,
            nodeUrl=node.url,
            nodeApiUrl=node.api_url,
        )
        root = result[0]
        assert_equal(root, expected)

    def test_root_is_slash(self):
        res = self.send_hook(
            'osf_storage_get_metadata_hook',
            {'path': '/'},
        )
        assert_equal(res.json, [])

    def test_metadata_not_found(self):
        res = self.send_hook(
            'osf_storage_get_metadata_hook',
            {'path': '/notfound'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 404)

    def test_metadata_not_found_lots_of_slashes(self):
        res = self.send_hook(
            'osf_storage_get_metadata_hook',
            {'path': '/not/fo/u/nd/'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 404)

    def test_metadata_path_required(self):
        res = self.send_hook(
            'osf_storage_get_metadata_hook', {},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)

    def test_metadata_path_empty(self):
        res = self.send_hook(
            'osf_storage_get_metadata_hook',
            {'path': ''},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)


class TestUploadFileHook(HookTestCase):

    def setUp(self):
        super(TestUploadFileHook, self).setUp()
        self.path = 'pízza.png'
        self.record = recursively_create_file(self.node_settings, self.path)
        self.auth = make_auth(self.user)

    def send_upload_hook(self, payload=None, **kwargs):
        return self.send_hook(
            'osf_storage_upload_file_hook',
            payload=payload or {},
            method='post_json',
            **kwargs
        )

    def make_payload(self, **kwargs):
        payload = {
            'auth': self.auth,
            'path': self.path,
            'hashes': {},
            'worker': '',
            'settings': {storage_settings.WATERBUTLER_RESOURCE: 'osf'},
            'metadata': {
                'provider': 'osfstorage',
                'service': 'cloud',
                'name': 'file',
                'size': 123,
                'modified': 'Mon, 16 Feb 2015 18:45:34 GMT'
            },
        }
        payload.update(kwargs)
        return payload

    def test_upload_create(self):
        path = 'slightly-mad'
        res = self.send_upload_hook(self.make_payload(path=path))
        self.record.reload()
        assert_equal(res.status_code, 201)
        assert_equal(res.json['status'], 'success')
        assert_equal(res.json['downloads'], self.record.get_download_count())
        version = model.OsfStorageFileVersion.load(res.json['version'])
        assert_is_not(version, None)
        assert_not_in(version, self.record.versions)
        record = self.node_settings.root_node.find_child_by_name(path)
        assert_in(version, record.versions)

    def test_upload_update(self):
        delta = Delta(lambda: len(self.record.versions), lambda value: value + 1)
        with AssertDeltas(delta):
            res = self.send_upload_hook(self.make_payload())
            self.record.reload()
        assert_equal(res.status_code, 200)
        assert_equal(res.json['status'], 'success')
        version = model.OsfStorageFileVersion.load(res.json['version'])
        assert_is_not(version, None)
        assert_in(version, self.record.versions)

    def test_upload_duplicate(self):
        location = {
            'service': 'cloud',
            storage_settings.WATERBUTLER_RESOURCE: 'osf',
            'object': 'file',
        }
        version = self.record.create_version(self.user, location)
        with AssertDeltas(Delta(lambda: len(self.record.versions))):
            res = self.send_upload_hook(self.make_payload())
            self.record.reload()
        assert_equal(res.status_code, 200)
        assert_equal(res.json['status'], 'success')
        version = model.OsfStorageFileVersion.load(res.json['version'])
        assert_is_not(version, None)
        assert_in(version, self.record.versions)

    def test_upload_create_child(self):
        name = 'pizza.png'
        parent = self.node_settings.root_node.append_folder('cheesey')
        path = os.path.join(parent.path, name)
        res = self.send_upload_hook(self.make_payload(path=path))

        assert_equal(res.status_code, 201)
        assert_equal(res.json['status'], 'success')
        assert_equal(res.json['downloads'], self.record.get_download_count())

        version = model.OsfStorageFileVersion.load(res.json['version'])

        assert_is_not(version, None)
        assert_not_in(version, self.record.versions)

        record = parent.find_child_by_name(name)
        assert_in(version, record.versions)
        assert_equals(record.name, name)
        assert_equals(record.parent, parent)

    def test_upload_weired_name(self):
        name = 'another/dir/carpe.png'
        parent = self.node_settings.root_node.append_folder('cheesey')
        path = os.path.join(parent.path, name)
        res = self.send_upload_hook(self.make_payload(path=path), expect_errors=True)

        assert_equal(res.status_code, 400)
        assert_equal(len(parent.children), 0)

    def test_upload_no_data(self):
        res = self.send_upload_hook(expect_errors=True)

        assert_equal(res.status_code, 400)

    # def test_upload_update_deleted(self):
    #     pass


class TestUpdateMetadataHook(HookTestCase):

    def setUp(self):
        super(TestUpdateMetadataHook, self).setUp()
        self.path = 'greasy/pízza.png'
        self.record = recursively_create_file(self.node_settings, self.path)
        self.version = factories.FileVersionFactory()
        self.record.versions = [self.version]
        self.record.save()
        self.payload = {
            'metadata': {'archive': 'glacier', 'size': 123, 'modified': 'Mon, 16 Feb 2015 18:45:34 GMT'},
            'version': self.version._id,
            'size': 123,
        }

    def send_metadata_hook(self, payload=None, **kwargs):
        return self.send_hook(
            'osf_storage_update_metadata_hook',
            payload=payload or self.payload,
            method='put_json',
            **kwargs
        )

    def test_archived(self):
        self.send_metadata_hook()
        self.version.reload()
        assert_in('archive', self.version.metadata)
        assert_equal(self.version.metadata['archive'], 'glacier')

    def test_archived_record_not_found(self):
        res = self.send_metadata_hook(
            payload={
                'metadata': {'archive': 'glacier'},
                'version': self.version._id[::-1],
                'size': 123,
                'modified': 'Mon, 16 Feb 2015 18:45:34 GMT'
            },
            expect_errors=True,
        )
        assert_equal(res.status_code, 404)
        self.version.reload()
        assert_not_in('archive', self.version.metadata)


class TestGetRevisions(StorageTestCase):

    def setUp(self):
        super(TestGetRevisions, self).setUp()
        self.path = 'tie/your/mother/down.mp3'
        self.record = self.node_settings.root_node.append_file(self.path)
        self.record.versions = [factories.FileVersionFactory() for __ in range(15)]
        self.record.save()

    def get_revisions(self, path=None, page=None, **kwargs):

        return self.app.get(
            self.project.api_url_for(
                'osf_storage_get_revisions',
                **signing.sign_data(
                    signing.default_signer,
                    {
                        'path': path or self.path,
                        'page': page,
                    }
                )
            ),
            auth=self.user.auth,
            **kwargs
        )

    def test_get_revisions_page_specified(self):
        res = self.get_revisions(path=self.path, page=1)
        expected = [
            utils.serialize_revision(
                self.project,
                self.record,
                self.record.versions[idx - 1],
                idx
            )
            for idx in range(5, 0, -1)
        ]
        assert_equal(res.json['revisions'], expected)
        assert_equal(res.json['more'], False)

    def test_get_revisions_page_not_specified(self):
        res = self.get_revisions(path=self.path)
        expected = [
            utils.serialize_revision(
                self.project,
                self.record,
                self.record.versions[idx - 1],
                idx
            )
            for idx in range(15, 5, -1)
        ]
        assert_equal(res.json['revisions'], expected)
        assert_equal(res.json['more'], True)

    def test_get_revisions_invalid_page(self):
        res = self.get_revisions(path=self.path, page='pizza', expect_errors=True)
        assert_equal(res.status_code, 400)

    def test_get_revisions_path_not_found(self):
        res = self.get_revisions(path='missing', expect_errors=True)
        assert_equal(res.status_code, 404)


def assert_urls_equal(url1, url2):
    furl1 = furl.furl(url1)
    furl2 = furl.furl(url2)
    for attr in ['scheme', 'host', 'port']:
        setattr(furl1, attr, None)
        setattr(furl2, attr, None)
    assert_equal(furl1, furl2)
