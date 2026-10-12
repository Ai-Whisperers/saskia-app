"""Regression guard: the La Vaquita seeder must use the real client data,
not the placeholder defaults from the pre-questionnaire draft.

Why this test exists:
- The 2026-10-08 onboarding questionnaire (Saskia's answers) provided
  the actual values for BUSINESS_INFO and SASKIA_* constants. Prior
  to SASKIA-213, the seeder used placeholder values (`hola@lavaquita.example`,
  `+595 21 555-1000`, `Av. España 1234...`, `Lunes a sábado 7:00-19:00...`,
  copyright 2025, name "Saskia Weiss") that never matched the real
  client.
- This test pins the new values so a future placeholder-regression
  (e.g. someone resets the dict for testing) fails CI.
- The test does NOT execute the seeder (which would touch the DB and
  is non-idempotent per the operator-script guard). It only imports
  the constants and asserts their values.

See docs/intake/SASKIA-213-vaquita-seed-data-update.md for context.
"""

from __future__ import annotations

import pytest

# Skip the entire module if sazon.py can't be imported (e.g. broken deps).
# The seeder module pulls in the full RMS model graph; this test should
# be runnable even when the seeder isn't fully importable in CI.
sazon = pytest.importorskip("app.rms.seed.sazon")


def test_business_info_address_matches_questionnaire_2_1():
    """§2.1: Laguán Grande, Arquitectos, Calle 17, Asunción."""
    assert sazon.BUSINESS_INFO["address"] == "Laguán Grande, Arquitectos, Calle 17, Asunción"


def test_business_info_phone_matches_questionnaire_2_3():
    """§2.3: +595 991 683805 (her WhatsApp)."""
    assert sazon.BUSINESS_INFO["phone"] == "+595 991 683805"


def test_business_info_email_matches_questionnaire_2_4():
    """§2.4: La.vaquitaholandesa@gmail.com."""
    assert sazon.BUSINESS_INFO["email"] == "La.vaquitaholandesa@gmail.com"


def test_business_info_business_hours_matches_questionnaire_2_7():
    """§2.7: Martes a sábado de 9 am a 6 pm (closed Sun + Mon)."""
    assert sazon.BUSINESS_INFO["business_hours"] == "Martes a sábado de 9 am a 6 pm"


def test_saskia_full_name_matches_questionnaire_4_1():
    """§4.1: Saskia Weiss Vander (full surname)."""
    assert sazon.SASKIA_FULL_NAME == "Saskia Weiss Vander"


def test_saskia_email_matches_questionnaire_4_3():
    """§4.3: La.vaquitaholandesa@gmail.com."""
    assert sazon.SASKIA_EMAIL == "La.vaquitaholandesa@gmail.com"


def test_saskia_user_unchanged():
    """§4.2: saskia (her username)."""
    assert sazon.SASKIA_USER == "saskia"


def test_no_placeholder_address_in_seeder():
    """The pre-questionnaire placeholder Av. España 1234 must not return."""
    full = " ".join(
        [
            sazon.BUSINESS_INFO.get("address", ""),
            sazon.BUSINESS_INFO.get("phone", ""),
            sazon.BUSINESS_INFO.get("email", ""),
        ]
    )
    assert "Av. España 1234" not in full
    assert "555-1000" not in full
    assert "@lavaquita.example" not in full


def test_cashier_users_block_has_documented_note():
    """§4.5 = "no cajeros". The seeder still hard-codes placeholder
    cashiers for the demo path; that mismatch must be documented inline
    so a future reader doesn't think it's the real user roster.
    """
    import inspect

    source = inspect.getsource(sazon)
    # Find the CASHIER_USERS block and verify it has the §4.5 note.
    assert "CASHIER_USERS" in source
    assert "SASKIA-214" in source, (
        "CASHIER_USERS block must reference SASKIA-214 (the follow-up "
        "ticket that makes the cashier list configurable per instance)"
    )
    assert "§4.5" in source, (
        "CASHIER_USERS block must reference questionnaire §4.5 (the "
        "data point that triggered the SASKIA-214 follow-up)"
    )
