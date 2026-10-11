def test_station_archive_marks_archived(authed_client, session_factory):
    """Archive action should mark station as deleted_at=now."""
    from app.rms.models import Station
    
    s = session_factory()
    station = Station(name="Test Archive")
    s.add(station)
    s.commit()
    sid = station.id
    s.close()

    response = authed_client.post(f"/station/{sid}/archive", follow_redirects=False)
    assert response.status_code == 303

    s = session_factory()
    archived_station = s.get(Station, sid)
    assert archived_station.deleted_at is not None
    s.close()


def test_station_unarchive_clears_archive_flag(authed_client, session_factory):
    """Unarchive action should clear deleted_at."""
    from app.rms.models import Station
    
    s = session_factory()
    station = Station(name="Test Unarchive", deleted_at="now")
    s.add(station)
    s.commit()
    sid = station.id
    s.close()

    response = authed_client.post(f"/station/{sid}/unarchive", follow_redirects=False)
    assert response.status_code == 303

    s = session_factory()
    unarchived_station = s.get(Station, sid)
    assert unarchived_station.deleted_at is None
    s.close()