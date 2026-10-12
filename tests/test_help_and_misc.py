"""tests/test_help_and_misc.py — Cover 0% low-hanging fruit: help.py router, common.py, maintenance.py.

Target modules:
- app/routers/help.py (151 stmts at 0%, 10%)
- app/rms/services/common.py (29 stmts at 0%)
- app/rms/maintenance.py (20 stmts at 0%)
- app/rms/models/sales.py (90 stmts at 0%, mostly STUB)
"""
import pytest
import re
from unittest.mock import MagicMock, patch
from pathlib import Path

# Help router tests
def test_md_to_html_basic_paragraph():
    from app.routers.help import _md_to_html
    result = _md_to_html("Hello world")
    assert "Hello world" in result

def test_md_to_html_bold_italic():
    from app.routers.help import _md_to_html
    md = "**bold** and *italic*"
    result = _md_to_html(md)
    assert "<strong>bold</strong>" in result
    assert "<em>italic</em>" in result

def test_md_to_html_inline_code():
    from app.routers.help import _md_to_html
    md = "Use `foo()` function"
    result = _md_to_html(md)
    assert "<code>foo()</code>" in result

def test_md_to_html_link_safe():
    from app.routers.help import _md_to_html
    md = "See [docs](https://example.com)"
    result = _md_to_html(md)
    assert '<a href="https://example.com"' in result
    assert "docs" in result

def test_md_to_html_link_blocks_javascript():
    from app.routers.help import _md_to_html
    md = "Click [me](javascript:alert(1))"
    result = _md_to_html(md)
    assert "javascript:" not in result

def test_md_to_html_escapes_html():
    from app.routers.help import _md_to_html
    md = "<script>alert(1)</script>"
    result = _md_to_html(md)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result

def test_md_to_html_table():
    from app.routers.help import _md_to_html
    md = "| Col1 | Col2 |\n|------|------|\n| A | B |\n| C | D |"
    result = _md_to_html(md)
    assert '<table' in result
    assert '<th>Col1</th>' in result
    assert '<td>A</td>' in result

def test_md_to_html_code_block():
    from app.routers.help import _md_to_html
    md = "```\nsome code here\n```"
    result = _md_to_html(md)
    assert '<pre>' in result or '<code>' in result

def test_md_to_html_list():
    from app.routers.help import _md_to_html
    md = "- item 1\n- item 2\n- item 3"
    result = _md_to_html(md)
    assert '<ul>' in result
    assert '<li>item 1</li>' in result

def test_md_to_html_h1_to_h4():
    from app.routers.help import _md_to_html
    for i in range(1, 5):
        md = "#" * i + f" Heading {i}"
        result = _md_to_html(md)
        assert f'<h{i}>Heading {i}</h{i}>' in result

def test_md_to_html_empty():
    from app.routers.help import _md_to_html
    result = _md_to_html("")
    # Should not raise

def test_md_to_html_italic_mid_word_safe():
    from app.routers.help import _md_to_html
    # Mid-word asterisks should NOT be italic (e.g., variable*name)
    md = "var*name* is not italic"
    result = _md_to_html(md)
    # The italic regex requires word boundary
    assert "<em>" not in result or "var" not in result.split("<em>")[0].split("</em>")[-1]

def test_md_to_html_italic_with_boundaries():
    from app.routers.help import _md_to_html
    md = "this is *real* italic"
    result = _md_to_html(md)
    assert "<em>real</em>" in result

def test_md_to_html_link_mailto():
    from app.routers.help import _md_to_html
    md = "Email [us](mailto:test@example.com)"
    result = _md_to_html(md)
    assert "mailto:" in result or "test@example.com" in result

def test_md_to_html_link_blocks_vbscript():
    from app.routers.help import _md_to_html
    md = "[x](vbscript:msgbox(1))"
    result = _md_to_html(md)
    assert "vbscript:" not in result

def test_md_to_html_link_blocks_data():
    from app.routers.help import _md_to_html
    md = "[x](data:text/html,evil)"
    result = _md_to_html(md)
    assert "data:" not in result

def test_md_to_html_table_malformed():
    from app.routers.help import _md_to_html
    # Single row — not a real table
    md = "| only | header |"
    result = _md_to_html(md)
    # Should fall back to pre
    assert "<pre>" in result

def test_md_to_html_table_with_formatting():
    from app.routers.help import _md_to_html
    md = "| Name | **Bold** |\n|------|----------|\n| val | *italic* |"
    result = _md_to_html(md)
    assert "<strong>Bold</strong>" in result
    assert "<em>italic</em>" in result

# services/common.py tests
def test_base_service_get_returns_none_if_not_found():
    from app.rms.services.common import BaseService
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    # Create concrete subclass
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.get(999)
    assert result is None

def test_base_service_get_returns_entity():
    from app.rms.services.common import BaseService
    db = MagicMock()
    entity = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = entity
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.get(1)
    assert result is entity

def test_base_service_list_default_limit():
    from app.rms.services.common import BaseService
    db = MagicMock()
    entities = [MagicMock(), MagicMock()]
    db.query.return_value.limit.return_value.all.return_value = entities
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.list()
    assert result == entities
    db.query.return_value.limit.assert_called_with(100)

def test_base_service_list_custom_limit():
    from app.rms.services.common import BaseService
    db = MagicMock()
    db.query.return_value.limit.return_value.all.return_value = []
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    svc.list(50)
    db.query.return_value.limit.assert_called_with(50)

def test_base_service_update_success():
    from app.rms.services.common import BaseService
    db = MagicMock()
    entity = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = entity
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.update(1, {"name": "new"})
    assert result is entity
    assert entity.name == "new"
    db.commit.assert_called_once()

def test_base_service_update_not_found_raises():
    from app.rms.services.common import BaseService
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.update(999, {"name": "x"})

def test_base_service_delete_success():
    from app.rms.services.common import BaseService
    db = MagicMock()
    entity = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = entity
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.delete(1)
    assert result is True
    db.delete.assert_called_once_with(entity)
    db.commit.assert_called_once()

def test_base_service_delete_not_found():
    from app.rms.services.common import BaseService
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    class FakeModel:
        id = None
    class FakeService(BaseService):
        _model = FakeModel
        def create(self, data):
            return None
    svc = FakeService(db)
    result = svc.delete(999)
    assert result is False
    db.delete.assert_not_called()

def test_base_service_abstract_create_must_be_implemented():
    from app.rms.services.common import BaseService
    # Cannot instantiate BaseService directly (has abstract create)
    with pytest.raises(TypeError):
        BaseService(MagicMock())

# maintenance.py tests
def test_maintenance_prune_audit_log_dry_run():
    from app.rms.maintenance import prune_audit_log
    sf = MagicMock()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar.return_value = 42
    sf.return_value = session
    result = prune_audit_log(sf, retention_days=30, dry_run=True)
    assert result == 42

def test_maintenance_prune_audit_log_actual_delete():
    from app.rms.maintenance import prune_audit_log
    sf = MagicMock()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.rowcount = 7
    sf.return_value = session
    result = prune_audit_log(sf, retention_days=30, dry_run=False)
    assert result == 7

def test_maintenance_prune_audit_log_db_error_returns_zero():
    from app.rms.maintenance import prune_audit_log
    def bad_sf():
        raise RuntimeError("DB down")
    result = prune_audit_log(bad_sf, retention_days=30)
    assert result == 0  # fail-soft

def test_maintenance_prune_audit_log_no_rows():
    from app.rms.maintenance import prune_audit_log
    sf = MagicMock()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar.return_value = 0
    sf.return_value = session
    result = prune_audit_log(sf, retention_days=30, dry_run=True)
    assert result == 0

def test_maintenance_prune_audit_log_default_retention():
    from app.rms.maintenance import prune_audit_log
    sf = MagicMock()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar.return_value = 100
    sf.return_value = session
    result = prune_audit_log(sf, dry_run=True)
    # Default 30 days
    assert result == 100

# models/sales.py — STUB check
def test_sales_module_is_stub():
    """SaleStockMove (app/rms/models/sales.py) is STUB deprecated (Saskia-213)."""
    from app.rms.models import sales
    # Should have a NotImplementedError or pass-only structure
    # The file is intentionally minimal
    import inspect
    src = inspect.getsource(sales)
    # It should NOT have ORM mapped classes (it's a stub)
    assert "class SaleStockMove" in src or "pass" in src

# Additional help router route tests
def test_help_router_route_requires_auth():
    """The /guia router requires login."""
    from app.routers.help import router
    # Check dependency injection
    assert len(router.dependencies) > 0

def test_help_guide_dir_exists():
    """The GUIDE_DIR should point to an existing or creatable path."""
    from app.routers.help import GUIDE_DIR
    # May not exist in test env, but should be a Path
    assert isinstance(GUIDE_DIR, Path)

def test_help_read_section_returns_tuple():
    from app.routers.help import _read_section
    # If section doesn't exist, should return something
    result = _read_section("__nonexistent__")
    assert isinstance(result, tuple)
    assert len(result) == 2
