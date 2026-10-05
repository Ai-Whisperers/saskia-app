"""Tests for T-10: mermas.html - notes column on events table"""

def test_mermas_page_shows_notes_column(authed_client):
    """Test that /mermas returns 200 and contains 'Notas' column"""
    response = authed_client.get("/merma")
    assert response.status_code == 200
    assert "Notas" in response.text
