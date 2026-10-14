# -*- coding: utf-8 -*-
"""Single shared password (HTTP Basic Auth) for the tool's private pages."""
import os
from functools import wraps

from flask import request

TOOL_PASSWORD = os.environ.get("TOOL_PASSWORD")


def require_password(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not TOOL_PASSWORD:
            return view(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.password != TOOL_PASSWORD:
            return (
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Order Intake"'},
            )
        return view(*args, **kwargs)

    return wrapped
