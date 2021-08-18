"""
Public views
"""


from django.shortcuts import redirect
from waffle.decorators import waffle_switch

from common.djangoapps.edxmako.shortcuts import render_to_response

from ..config import waffle

__all__ = ['howitworks', 'accessibility']


def howitworks(request):
    "Proxy view"
    if request.user.is_authenticated:
        return redirect('/home/')
    else:
        return render_to_response('howitworks.html', {})


@waffle_switch(f'{waffle.WAFFLE_NAMESPACE}.{waffle.ENABLE_ACCESSIBILITY_POLICY_PAGE}')
def accessibility(request):
    """
    Display the accessibility accommodation form.
    """

    return render_to_response('accessibility.html', {
        'language_code': request.LANGUAGE_CODE
    })
