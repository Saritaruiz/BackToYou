from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def administrator_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

        if (
            not request.user.is_active
            or request.user.role != User.Role.ADMINISTRATOR
        ):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return _wrapped_view
