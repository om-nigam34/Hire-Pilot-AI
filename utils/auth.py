import re
from functools import wraps
from flask import session, redirect, url_for, jsonify, request, g
from werkzeug.security import generate_password_hash, check_password_hash

from utils import db

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


#  Passwords 

def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


#  Signup validation 

def validate_signup(username: str, email: str, password: str, confirm_password: str) -> str | None:
    # Returns an error message string, or None if everything checks out.
    if not _USERNAME_RE.match(username or ""):
        return "Username must be 3-32 characters - letters, numbers, and underscores only."
    if not _EMAIL_RE.match(email or ""):
        return "Enter a valid email address."
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    if password != confirm_password:
        return "Passwords don't match."
    return None


#  Current user helpers 

def _resolve_user_from_session() -> dict | None:
    # A cookie can outlive the account it points to - a local db reset
    # while a browser still holds an old session, or a deleted account in
    # production. So we always check the id against the db, not just
    # trust that the cookie has *a* user_id in it.
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.get_user_by_id(user_id)


def get_current_user() -> dict | None:
    # Cached on Flask's request-scoped `g`, so a decorator and the route
    # it wraps don't each run a separate db lookup for the same user.
    if "user" not in g:
        g.user = _resolve_user_from_session()
    return g.user


def login_required(view):
    # Protects full-page routes. Not logged in, or the session points to
    # an account that no longer exists -> clear the bad cookie and bounce
    # to /login, remembering where they were headed so we can send them
    # back after.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            session.clear()
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def api_login_required(view):
    # Protects JSON API routes. Same check as login_required, but a 401
    # JSON body instead of a redirect, since the frontend JS expects JSON
    # back either way.
    @wraps(view)
    def wrapped(*args, **kwargs):
        if get_current_user() is None:
            session.clear()
            return jsonify(error="Please log in to continue."), 401
        return view(*args, **kwargs)
    return wrapped