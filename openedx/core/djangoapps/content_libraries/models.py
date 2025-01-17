"""
Models for new Content Libraries.
"""

import contextlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import ugettext_lazy as _

from opaque_keys.edx.django.models import CourseKeyField
from opaque_keys.edx.locator import LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.constants import (
    LIBRARY_TYPES, COMPLEX, LICENSE_OPTIONS,
    ALL_RIGHTS_RESERVED,
)
from organizations.models import Organization  # lint-amnesty, pylint: disable=wrong-import-order

User = get_user_model()


class ContentLibraryManager(models.Manager):
    """
    Custom manager for ContentLibrary class.
    """
    def get_by_key(self, library_key):
        """
        Get the ContentLibrary for the given LibraryLocatorV2 key.
        """
        assert isinstance(library_key, LibraryLocatorV2)
        return self.get(org__short_name=library_key.org, slug=library_key.slug)


class ContentLibrary(models.Model):
    """
    A Content Library is a collection of content (XBlocks and/or static assets)

    All actual content is stored in Blockstore, and any data that we'd want to
    transfer to another instance if this library were exported and then
    re-imported on another Open edX instance should be kept in Blockstore. This
    model in the LMS should only be used to track settings specific to this Open
    edX instance, like who has permission to edit this content library.
    """
    objects = ContentLibraryManager()

    id = models.AutoField(primary_key=True)
    # Every Library is uniquely and permanently identified by an 'org' and a
    # 'slug' that are set during creation/import. Both will appear in the
    # library's opaque key:
    # e.g. "lib:org:slug" is the opaque key for a library.
    org = models.ForeignKey(Organization, on_delete=models.PROTECT, null=False)
    slug = models.SlugField(allow_unicode=True)
    bundle_uuid = models.UUIDField(unique=True, null=False)
    type = models.CharField(max_length=25, default=COMPLEX, choices=LIBRARY_TYPES)
    license = models.CharField(max_length=25, default=ALL_RIGHTS_RESERVED, choices=LICENSE_OPTIONS)

    # How is this library going to be used?
    allow_public_learning = models.BooleanField(
        default=False,
        help_text=("""
            Allow any user (even unregistered users) to view and interact with
            content in this library (in the LMS; not in Studio). If this is not
            enabled, then the content in this library is not directly accessible
            in the LMS, and learners will only ever see this content if it is
            explicitly added to a course. If in doubt, leave this unchecked.
        """),
    )
    allow_public_read = models.BooleanField(
        default=False,
        help_text=("""
            Allow any user with Studio access to view this library's content in
            Studio, use it in their courses, and copy content out of this
            library. If in doubt, leave this unchecked.
        """),
    )

    class Meta:
        verbose_name_plural = "Content Libraries"
        unique_together = ("org", "slug")

    @property
    def library_key(self):
        """
        Get the LibraryLocatorV2 opaque key for this library
        """
        return LibraryLocatorV2(org=self.org.short_name, slug=self.slug)

    def __str__(self):
        return f"ContentLibrary ({str(self.library_key)})"


class ContentLibraryPermission(models.Model):
    """
    Row recording permissions for a content library
    """
    library = models.ForeignKey(ContentLibrary, on_delete=models.CASCADE, related_name="permission_grants")
    # One of the following must be set (but not both):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    # What level of access is granted to the above user or group:
    ADMIN_LEVEL = 'admin'
    AUTHOR_LEVEL = 'author'
    READ_LEVEL = 'read'
    ACCESS_LEVEL_CHOICES = (
        (ADMIN_LEVEL, _("Administer users and author content")),
        (AUTHOR_LEVEL, _("Author content")),
        (READ_LEVEL, _("Read-only")),
    )
    access_level = models.CharField(max_length=30, choices=ACCESS_LEVEL_CHOICES)

    class Meta:
        ordering = ('user__username', 'group__name')
        unique_together = [
            ('library', 'user'),
            ('library', 'group'),
        ]

    def save(self, *args, **kwargs):  # lint-amnesty, pylint: disable=arguments-differ, signature-differs
        """
        Validate any constraints on the model.

        We can remove this and replace it with a proper database constraint
        once we're upgraded to Django 2.2+
        """
        # if both are nonexistent or both are existing, error
        if (not self.user) == (not self.group):
            raise ValidationError(_("One and only one of 'user' and 'group' must be set."))
        return super().save(*args, **kwargs)

    def __str__(self):
        who = self.user.username if self.user else self.group.name
        return f"ContentLibraryPermission ({self.access_level} for {who})"


class ContentLibraryBlockImportTask(models.Model):
    """
    Model of a task to import blocks from an external source (e.g. modulestore).
    """

    library = models.ForeignKey(
        ContentLibrary,
        on_delete=models.CASCADE,
        related_name='import_tasks',
    )

    TASK_CREATED = 'created'
    TASK_PENDING = 'pending'
    TASK_RUNNING = 'running'
    TASK_FAILED = 'failed'
    TASK_SUCCESSFUL = 'successful'

    TASK_STATE_CHOICES = (
        (TASK_CREATED, _('Task was created, but not queued to run.')),
        (TASK_PENDING, _('Task was created and queued to run.')),
        (TASK_RUNNING, _('Task is running.')),
        (TASK_FAILED, _('Task finished, but some blocks failed to import.')),
        (TASK_SUCCESSFUL, _('Task finished successfully.')),
    )

    state = models.CharField(
        choices=TASK_STATE_CHOICES,
        default=TASK_CREATED,
        max_length=30,
        verbose_name=_('state'),
        help_text=_('The state of the block import task.'),
    )

    progress = models.FloatField(
        default=0.0,
        verbose_name=_('progress'),
        help_text=_('A float from 0.0 to 1.0 representing the task progress.'),
    )

    course_id = CourseKeyField(
        max_length=255,
        db_index=True,
        verbose_name=_('course ID'),
        help_text=_('ID of the imported course.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-updated_at']

    @classmethod
    @contextlib.contextmanager
    def execute(cls, import_task_id):
        """
        A context manager to manage a task that is being executed.
        """
        self = cls.objects.get(pk=import_task_id)
        self.state = self.TASK_RUNNING
        self.save()
        try:
            yield self
            self.state = self.TASK_SUCCESSFUL
        except:  # pylint: disable=broad-except
            self.state = self.TASK_FAILED
            raise
        finally:
            self.save()

    def save_progress(self, progress):
        self.progress = progress
        self.save(update_fields=['progress', 'updated_at'])

    def __str__(self):
        return f'{self.course_id} to {self.library} #{self.pk}'
