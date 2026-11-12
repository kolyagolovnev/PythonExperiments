"""Fixed resource admins, defined in a JSON file (not in the database).

An admin's email listed here gets the admin role at signup/signin time.
"""

import json
from pathlib import Path


class AdminRegistry:
    def __init__(self, emails: set[str] | None = None):
        self._emails = {email.lower() for email in (emails or set())}

    @classmethod
    def from_file(cls, path: Path) -> "AdminRegistry":
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(set(data.get("admins", [])))

    def is_admin(self, email: str) -> bool:
        return email.lower() in self._emails
