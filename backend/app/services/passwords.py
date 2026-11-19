"""Password policy for passwords set through the API (user creation and admin resets).

Rules (aligned with NIST SP 800-63B's emphasis on length and blocklists, plus a modest
character-variety rule):
* 10 to 128 characters;
* at least three of: lowercase, uppercase, digit, symbol;
* not a commonly used password;
* must not contain the user's email name or a part of their name.
"""

from __future__ import annotations

import re

MIN_LENGTH = 10
MAX_LENGTH = 128

# A short blocklist of the most common choices (case-insensitive). Production systems would
# check a large breached-password corpus instead.
COMMON_PASSWORDS = {
    "password",
    "password1",
    "password123",
    "password@123",
    "passw0rd",
    "qwerty123",
    "qwertyuiop",
    "1234567890",
    "12345678910",
    "123456789a",
    "iloveyou123",
    "welcome123",
    "welcome@123",
    "letmein123",
    "admin12345",
    "administrator",
    "changeme123",
    "accesshub123",
}

_CLASSES = (
    (re.compile(r"[a-z]"), "lowercase letter"),
    (re.compile(r"[A-Z]"), "uppercase letter"),
    (re.compile(r"\d"), "digit"),
    (re.compile(r"[^A-Za-z0-9]"), "symbol"),
)


def password_problems(password: str, *, email: str | None = None, name: str | None = None) -> list[str]:
    """Everything wrong with ``password`` (empty list = acceptable)."""
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use at most {MAX_LENGTH} characters.")
    if sum(1 for pattern, _ in _CLASSES if pattern.search(password)) < 3:
        problems.append("Use at least three of: lowercase letters, uppercase letters, digits, symbols.")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        problems.append("This password is too common.")

    personal = []
    if email:
        personal.append(email.split("@")[0].lower())
    if name:
        personal.extend(part.lower() for part in re.split(r"\W+", name))
    if any(len(part) >= 3 and part in lowered for part in personal):
        problems.append("Don't include your name or email in your password.")
    return problems
