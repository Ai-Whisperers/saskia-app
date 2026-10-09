"""Extracted from conftest (C1): shared Supabase fake."""


def _FakeSupabaseForIntegration():
    """Factory — instantiated once per fixture for test isolation."""

    class Fake:
        def __init__(self):
            self.users: dict[str, str] = {}
            self._tokens: dict[str, dict] = {}
            self._refresh: dict[str, str] = {}
            self.reset_called: list[str] = []

        def sign_in_with_password(self, creds):
            email = creds.get("username") or creds.get("email")
            pw = creds.get("password", "")
            if self.users.get(email) != pw:
                raise Exception("Invalid login credentials")
            import uuid

            uid = str(uuid.uuid4())
            self._tokens[uid] = {
                "access_token": f"fake-access-{uid}",
                "refresh_token": f"fake-refresh-{uid}",
                "user_id": uid,
                "email": email,
            }
            self._refresh[uid] = f"fake-refresh-{uid}"
            return self._tokens[uid]

        def refresh_session(self, refresh_token):
            for data in self._tokens.values():
                if data["refresh_token"] == refresh_token:
                    return data
            raise Exception("Invalid refresh token")

        def get_user(self, token):
            for data in self._tokens.values():
                if data["access_token"] == token:
                    return {"id": data["user_id"], "email": data["email"]}
            raise Exception("Invalid token")

        def sign_out(self, token):
            pass

        def reset(self):
            self._tokens.clear()
            self._refresh.clear()

        @property
        def auth(self):
            return self

    return Fake()
