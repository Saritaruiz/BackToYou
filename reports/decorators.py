from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import ItemReport


def report_owner_required(view_func):
    """Allow the view only for the authenticated creator of the report.

    The report captured by the URL is resolved here and passed to the view as
    its `report` argument, replacing `report_id`.
    """

    @wraps(view_func)
    def _wrapped_view(request, report_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

        report = get_object_or_404(ItemReport, id=report_id)

        if report.creator != request.user:
            raise PermissionDenied("You can only manage your own reports.")

        return view_func(request, report, *args, **kwargs)

    return _wrapped_view
