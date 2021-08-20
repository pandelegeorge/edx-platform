"""
Provider state views needed by pact to setup Provider state for pact verification.
"""
import json
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.tests.django_utils import TEST_DATA_SPLIT_MODULESTORE, ModuleStoreIsolationMixin
from xmodule.modulestore.tests.factories import ToyCourseFactory

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from openedx.features.course_duration_limits.models import CourseDurationLimitConfig


class ProviderState(ModuleStoreIsolationMixin):
    """ Provider State Setup """

    MODULESTORE = TEST_DATA_SPLIT_MODULESTORE

    def clean_db(self, user, course_key):
        """ Utility method to clean db """

        CourseEnrollment.objects.filter(course_id=course_key, user=user).delete()
        CourseMode.objects.filter(course_id=course_key).delete()

        try:
            self.end_modulestore_isolation()
        except IndexError:
            pass

    def course_setup(self, request):
        """ Setup course data """

        course_key = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')

        self.clean_db(request.user, course_key)
        self.start_modulestore_isolation()

        demo_course = ToyCourseFactory.create(
            org=course_key.org,
            course=course_key.course,
            run=course_key.run,
            display_name="Demonstration Course",
            modulestore=self.store,
            start=datetime(2024, 1, 1, 1, 1, 1),
            end=datetime(2028, 1, 1, 1, 1, 1),
            enrollment_start=datetime(2020, 1, 1, 1, 1, 1),
            enrollment_end=datetime(2028, 1, 1, 1, 1, 1),
            license="all-rights-reserved",
        )

        CourseModeFactory(
            course_id=demo_course.id,
            mode_slug=CourseMode.AUDIT,
        )

        CourseModeFactory(
            course_id=demo_course.id,
            mode_slug=CourseMode.VERIFIED,
            expiration_datetime=datetime(3028, 1, 1),
            min_price=149,
            sku='ABCD1234',
        )

        CourseEnrollment.enroll(request.user, demo_course.id, CourseMode.AUDIT)
        CourseDurationLimitConfig.objects.create(enabled=True, enabled_as_of=datetime(2018, 1, 1))


@csrf_exempt
@require_POST
def provider_state(request):
    """
    Provider state setup view needed by pact verifier.
    """
    state_setup_mapping = {
        'course metadata exists for course_id course-v1:edX+DemoX+Demo_Course': ProviderState().course_setup
    }
    request_body = json.loads(request.body)
    state = request_body.get('state')

    if state in state_setup_mapping:
        print('Setting up provider state for state value: {}'.format(state))
        state_setup_mapping[state](request)

    return JsonResponse({'result': state})
