from typing import Any

from app.rms.db import _bump_schema_version


def _migration_005_customer(conn: Any) -> None:
    """Add Customer table + Sale.customer_id FK (E13).

    Tables are created via create_all() in init_db(). The Sale
    FK column is added in case create_all didn't (e.g. on an existing
    DB that pre-dates the customer table).
    """
    _bump_schema_version(conn, 5)
