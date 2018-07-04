from typing import Set

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

import os
import subprocess
import zipfile

from threading import Thread

from imagetagger.users.models import Team


class Image(models.Model):
    image_set = models.ForeignKey(
        'ImageSet', on_delete=models.CASCADE, related_name='images')
    name = models.CharField(max_length=100)
    filename = models.CharField(max_length=100, unique=True)
    time = models.DateTimeField(auto_now_add=True)
    checksum = models.BinaryField()
    width = models.IntegerField(default=800)
    height = models.IntegerField(default=600)

    def path(self):
        return os.path.join(self.image_set.root_path(), self.filename)

    def relative_path(self):
        return os.path.join(self.image_set.path, self.filename)

    def delete(self, using=None, keep_parents=False):
        os.remove(os.path.join(settings.IMAGE_PATH, self.path()))
        self.image_set.update_zip()
        super(Image, self).delete(using, keep_parents)

    def save(self, zip=True, force_insert=False, force_update=False, using=None,
             update_fields=None):
        super(Image, self).save(force_insert, force_update, using, update_fields)
        if zip:
            self.image_set.update_zip()

    def __str__(self):
        return u'Image: {0}'.format(self.name)


class ImageSet(models.Model):
    class Meta:
        unique_together = [
            'name',
            'team',
        ]
    PRIORITIES = (
        (1, 'High'),
        (0, 'Normal'),
        (-1, 'Low'),
    )

    path = models.CharField(max_length=100, unique=True, null=True)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(max_length=1000, null=True, blank=True)
    time = models.DateTimeField(auto_now_add=True)
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        related_name='image_sets',
        null=True,
    )
    creator = models.ForeignKey(settings.AUTH_USER_MODEL,
                                default=None,
                                on_delete=models.SET_NULL,
                                null=True,
                                blank=True)
    public = models.BooleanField(default=False)
    public_collaboration = models.BooleanField(default=False)
    image_lock = models.BooleanField(default=False)
    priority = models.IntegerField(choices=PRIORITIES, default=0)
    main_annotation_type = models.ForeignKey(
        to='annotations.AnnotationType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None
    )
    pinned_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='pinned_sets')
    zip_finished = models.BooleanField(default=True)

    def root_path(self):
        return os.path.join(settings.IMAGE_PATH, self.path)

    def zip_file_exists(self):
        return os.path.isfile(self.zip_path())

    def zip_path(self):
        return os.path.join(settings.IMAGE_PATH, self.relative_zip_path())

    def relative_zip_path(self):
        return os.path.join(self.path, self.name) + '.zip'

    def _update_zip_thread(self):
        self.zip_finished = False
        self.save()

        # The python standard library module 'zipfile' is used for
        # the zipping process. It allows adding of files with a
        # different file name in the zip file which is crucial because
        # the internal store process adds random strings to the
        # filename that should not appear in the zip archive.
        # Unfortunately, the module does not support deletion of
        # single files in the archive. Therefore, the 'zip' command
        # line tool is called as a subprocess.

        with zipfile.ZipFile(self.zip_path(), 'a') as f:
            contents = f.namelist()
            # Add missing image to the archive
            for image in self.images.all():
                if image.name in contents:
                    contents.remove(image.name)
                else:
                    f.write(image.path(), image.name)

        # Remove deleted images
        if len(contents) > 0:
            command = ['zip', '-d', self.zip_path()] + contents
            subprocess.run(command)

        self.zip_finished = True
        self.save()

    def update_zip(self, threading=True):
        # Threading is used to avoid interrupting the user for the
        # potentially long zip file creation. Sometimes though, the
        # user should have to wait (e. g. for a download), hence the
        # 'threading' parameter.
        if threading:
            t = Thread(target=self._update_zip_thread)
            t.start()
        else:
            self._update_zip_thread()

    @property
    def image_count(self):
        if hasattr(self, 'image_count_agg'):
            return self.image_count_agg
        return self.images.count()

    def get_perms(self, user: get_user_model()) -> Set[str]:
        """Get all permissions of the user."""
        perms = set()
        if self.team is not None:
            if self.team.is_admin(user):
                perms.update({
                    'verify',
                    'annotate',
                    'create_export',
                    'delete_annotation',
                    'delete_export',
                    'delete_set',
                    'delete_images',
                    'edit_annotation',
                    'edit_set',
                    'read',
                })
            if self.team.is_member(user):
                perms.update({
                    'verify',
                    'annotate',
                    'create_export',
                    'delete_annotation',
                    'delete_export',
                    'edit_annotation',
                    'edit_set',
                    'read',
                })
            if user == self.creator:
                perms.update({
                    'verify',
                    'annotate',
                    'create_export',
                    'delete_annotation',
                    'delete_export',
                    'delete_set',
                    'delete_images',
                    'edit_annotation',
                    'edit_set',
                    'read',
                })
        if self.public:
            perms.update({
                'read',
                'create_export',
            })
            if self.public_collaboration:
                perms.update({
                    'verify',
                    'annotate',
                    'delete_annotation',
                    'edit_annotation',
                })
        return perms

    def has_perm(self, permission: str, user: get_user_model()) -> bool:
        """Check whether user has specified permission."""
        return permission in self.get_perms(user)

    def __str__(self):
        return u'Imageset: {0}'.format(self.name)

    @property
    def prio_symbol(self):
        if self.priority is -1:
            return '<span class="glyphicon glyphicon-download" data-toggle="tooltip" data-placement="right" title="Low labeling priority"></span>'
        elif self.priority is 0:
            return ''
        elif self.priority is 1:
            return '<span class="glyphicon glyphicon-exclamation-sign" data-toggle="tooltip" data-placement="right" title="High labeling priority"></span>'


class SetTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    imagesets = models.ManyToManyField(ImageSet, related_name='set_tags')
