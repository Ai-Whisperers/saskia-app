"""tests/test_dashboard_compliance.py — Phase 1.A compliance alerts on dashboard."""
from __future__ import annotations

from datetime import date, timedelta

from app.rms.config import ASUNCION_TZ
from app.rms.models import ComplianceInfo, Product


def _asuncion_today() -> date:
    """Route under test computes vs Asuncion date (not host UTC date).

    Seeding with datetime.utcnow().date() diverges near midnight UTC and flakes the
    day count by one.
    """
    from datetime import datetime, timezone

    return datetime.now(ASUNCION_TZ).date()
from app.routers.dashboard import _compliance_alerts


class TestComplianceAlertsEmpty:
    def test_no_alerts_when_compliance_info_not_set(self, session_factory):
        """When RUC + INAN R.E. + Director Técnico are all missing, return an info alert."""
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_number = ""
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            ci.ruc = ""
            ci.director_tecnico = ""
            ci.tax_regime = "no_libreta"  # no timbrado required
            s.commit()
            alerts = _compliance_alerts(s)
        # Should produce 1 info-level alert about missing required fields
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "info"
        assert "RUC" in alerts[0]["message"]


class TestInanREExpiry:
    def test_inan_re_expired_30_days_ago(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_number = "8000/2024"
            ci.inan_re_expiry = (_asuncion_today() - timedelta(days=30)).isoformat()
            s.commit()
            alerts = _compliance_alerts(s)
        inan_alerts = [a for a in alerts if "INAN R.E." in a["message"]]
        assert len(inan_alerts) == 1
        assert inan_alerts[0]["severity"] == "danger"
        assert "30 días" in inan_alerts[0]["message"]

    def test_inan_re_expires_in_15_days(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_number = "8000/2024"
            ci.inan_re_expiry = (_asuncion_today() + timedelta(days=15)).isoformat()
            s.commit()
            alerts = _compliance_alerts(s)
        inan_alerts = [a for a in alerts if "INAN R.E." in a["message"]]
        assert len(inan_alerts) == 1
        assert inan_alerts[0]["severity"] == "warn"
        assert "15 días" in inan_alerts[0]["message"]

    def test_inan_re_expires_in_60_days_no_alert(self, session_factory):
        """More than 30 days out → no alert (just OK)."""
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_number = "8000/2024"
            ci.inan_re_expiry = (datetime.utcnow().date() + timedelta(days=60)).isoformat()
            s.commit()
            alerts = _compliance_alerts(s)
        inan_alerts = [a for a in alerts if "INAN R.E." in a["message"]]
        assert len(inan_alerts) == 0


class TestTimbradoExpiry:
    def test_timbrado_expired(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.tax_regime = "resimple"
            ci.timbrado_number = "12345678"
            ci.timbrado_expiry = (datetime.utcnow().date() - timedelta(days=5)).isoformat()
            s.commit()
            alerts = _compliance_alerts(s)
        timbrado_alerts = [a for a in alerts if "Timbrado" in a["message"]]
        assert len(timbrado_alerts) == 1
        assert timbrado_alerts[0]["severity"] == "danger"


class TestMunicipalExpiry:
    def test_municipal_habilitacion_expiring_soon(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.municipal_habilitacion = "HAB-2024-001234"
            ci.municipal_habilitacion_expiry = (datetime.utcnow().date() + timedelta(days=7)).isoformat()
            s.commit()
            alerts = _compliance_alerts(s)
        hab_alerts = [a for a in alerts if "Habilitación" in a["message"]]
        assert len(hab_alerts) == 1
        assert hab_alerts[0]["severity"] == "warn"


class TestRSPAPerProduct:
    def test_rspa_expired_product_shows_alert(self, session_factory):
        Session = session_factory
        with Session() as s:
            # Clear all compliance_info dates so we don't get extra alerts
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            # Add a product with expired R.S.P.A.
            p = Product(
                name="Pan lactal 500g",
                sale_price_gs=12000,
                portion_label="500g",
                requires_rspa=True,
                rspa_number="12345/2024",
                rspa_expiry=(datetime.utcnow().date() - timedelta(days=10)).isoformat(),
            )
            s.add(p)
            s.commit()
            alerts = _compliance_alerts(s)
        rspa_alerts = [a for a in alerts if "R.S.P.A." in a["message"] and "Pan lactal" in a["message"]]
        assert len(rspa_alerts) == 1
        assert rspa_alerts[0]["severity"] == "danger"

    def test_rspa_expiring_in_20_days(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            p = Product(
                name="Bizcocho 250g",
                sale_price_gs=8500,
                portion_label="250g",
                requires_rspa=True,
                rspa_number="99999/2024",
                rspa_expiry=(datetime.utcnow().date() + timedelta(days=20)).isoformat(),
            )
            s.add(p)
            s.commit()
            alerts = _compliance_alerts(s)
        rspa_alerts = [a for a in alerts if "R.S.P.A." in a["message"]]
        assert len(rspa_alerts) == 1
        assert rspa_alerts[0]["severity"] == "warn"

    def test_rspa_field_set_but_requires_rspa_false_no_alert(self, session_factory):
        """If requires_rspa=False, the rspa_expiry is meaningless → no alert."""
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            p = Product(
                name="Mostrador bread",
                sale_price_gs=5000,
                portion_label="1 und",
                requires_rspa=False,
                rspa_expiry=(datetime.utcnow().date() - timedelta(days=100)).isoformat(),
            )
            s.add(p)
            s.commit()
            alerts = _compliance_alerts(s)
        rspa_alerts = [a for a in alerts if "R.S.P.A." in a["message"]]
        assert len(rspa_alerts) == 0


class TestMissingComplianceInfo:
    def test_missing_ruc_shows_info_alert(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.ruc = ""
            ci.inan_re_number = ""
            ci.director_tecnico = ""
            ci.tax_regime = "no_libreta"  # no timbrado required
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            s.commit()
            alerts = _compliance_alerts(s)
        missing_alerts = [a for a in alerts if a["severity"] == "info"]
        assert len(missing_alerts) >= 1
        assert "RUC" in missing_alerts[0]["message"]
        assert "INAN R.E." in missing_alerts[0]["message"]
        assert "Director Técnico" in missing_alerts[0]["message"]

    def test_resimple_missing_timbrado_triggers_info_alert(self, session_factory):
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.ruc = "80012345-6"
            ci.inan_re_number = "8000/2024"
            ci.director_tecnico = "Juan"
            ci.tax_regime = "resimple"
            ci.timbrado_number = ""
            ci.inan_re_expiry = None
            ci.municipal_habilitacion_expiry = None
            ci.timbrado_expiry = None
            s.commit()
            alerts = _compliance_alerts(s)
        info_alerts = [a for a in alerts if a["severity"] == "info"]
        assert any("Timbrado" in a["message"] for a in info_alerts)

    def test_iso_date_with_invalid_format_no_alert(self, session_factory):
        """Malformed dates should be ignored (not crash)."""
        Session = session_factory
        with Session() as s:
            ci = s.get(ComplianceInfo, 1)
            ci.inan_re_number = "8000/2024"
            ci.inan_re_expiry = "not-a-date"
            s.commit()
            alerts = _compliance_alerts(s)
        inan_alerts = [a for a in alerts if "INAN R.E." in a["message"]]
        assert len(inan_alerts) == 0
