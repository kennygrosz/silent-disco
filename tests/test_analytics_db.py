"""Tests for services/analytics_db.py - SQLite analytics persistence."""

import pytest
from datetime import datetime, timedelta
from models.snippet import Snippet, SnippetState
from services.analytics_db import AnalyticsDB


@pytest.fixture
def db(tmp_path):
    """Create a fresh AnalyticsDB in a temp directory."""
    db = AnalyticsDB(db_path=str(tmp_path / 'test.db'))
    yield db
    db.close()


def _make_snippet(tmp_path, state='queued', artist='Test Artist', name='Test Song',
                  album_art_url='https://example.com/art.jpg', track_string=None,
                  timestamp=None):
    """Helper to create a snippet in a specific state."""
    snip = Snippet(output_folder=str(tmp_path), snippet_duration=5)
    if timestamp:
        snip.timestamp = timestamp
    snip.mark_recorded()

    if state in ('recognized', 'queueable', 'queued'):
        snip.mark_recognized(track_string or f"{artist} - {name}")
        snip.set_spotify_info(
            song_id='abc123', song_uri='spotify:track:abc123',
            song_name=name, song_artist=artist,
            duration_ms=240000, album_art_url=album_art_url
        )
    if state == 'queueable':
        snip.mark_queueable()
    elif state == 'queued':
        snip.mark_queueable()
        snip.mark_queued()
    elif state == 'unrecognized':
        snip.mark_unrecognized()
    elif state == 'failed':
        snip.mark_failed()

    return snip


class TestTableCreation:
    def test_creates_tables_on_init(self, db):
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {r['name'] for r in tables}
        assert 'sessions' in table_names
        assert 'snippets' in table_names

    def test_idempotent_table_creation(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        db1 = AnalyticsDB(db_path=db_path)
        session_id = db1.start_session()
        db1.close()

        db2 = AnalyticsDB(db_path=db_path)
        sessions = db2.conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
        assert sessions == 1
        db2.close()


class TestSessionLifecycle:
    def test_start_session_returns_id(self, db):
        session_id = db.start_session()
        assert isinstance(session_id, int)
        assert session_id > 0

    def test_end_session_sets_ended_at(self, db):
        session_id = db.start_session()
        db.end_session(session_id)

        row = db.conn.execute(
            'SELECT ended_at FROM sessions WHERE id = ?', (session_id,)
        ).fetchone()
        assert row['ended_at'] is not None

    def test_end_session_updates_snippet_count(self, db, tmp_path):
        session_id = db.start_session()
        for _ in range(3):
            snip = _make_snippet(tmp_path)
            db.record_snippet(session_id, snip, played_on_spotify=True, blocked=False)
        db.end_session(session_id)

        row = db.conn.execute(
            'SELECT snippet_count FROM sessions WHERE id = ?', (session_id,)
        ).fetchone()
        assert row['snippet_count'] == 3

    def test_multiple_sessions(self, db):
        id1 = db.start_session()
        id2 = db.start_session()
        assert id1 != id2


class TestRecordSnippet:
    def test_record_recognized_snippet(self, db, tmp_path):
        session_id = db.start_session()
        snip = _make_snippet(tmp_path, state='queued')
        db.record_snippet(session_id, snip, played_on_spotify=True, blocked=False)

        row = db.conn.execute('SELECT * FROM snippets WHERE id = 1').fetchone()
        assert row['song_name'] == 'Test Song'
        assert row['song_artist'] == 'Test Artist'
        assert row['played_on_spotify'] == 1
        assert row['blocked'] == 0
        assert row['state'] == 'queued'

    def test_record_unrecognized_snippet(self, db, tmp_path):
        session_id = db.start_session()
        snip = _make_snippet(tmp_path, state='unrecognized')
        db.record_snippet(session_id, snip, played_on_spotify=False, blocked=False)

        row = db.conn.execute('SELECT * FROM snippets WHERE id = 1').fetchone()
        assert row['state'] == 'unrecognized'
        assert row['song_name'] is None
        assert row['played_on_spotify'] == 0

    def test_record_blocked_snippet(self, db, tmp_path):
        session_id = db.start_session()
        snip = _make_snippet(tmp_path, state='recognized')
        db.record_snippet(session_id, snip, played_on_spotify=False, blocked=True)

        row = db.conn.execute('SELECT * FROM snippets WHERE id = 1').fetchone()
        assert row['blocked'] == 1
        assert row['played_on_spotify'] == 0


class TestGetAnalytics:
    def test_empty_database(self, db):
        data = db.get_analytics()
        assert data['total_snippets'] == 0
        assert data['recognition_rate'] == 0
        assert data['top_artists'] == []
        assert data['top_songs'] == []
        assert len(data['by_hour']) == 24
        assert len(data['by_day']) == 7
        assert all(v == 0 for v in data['by_hour'])
        assert all(v == 0 for v in data['by_day'])

    def test_recognition_rate(self, db, tmp_path):
        session_id = db.start_session()
        for _ in range(3):
            db.record_snippet(session_id, _make_snippet(tmp_path, state='queued'),
                              played_on_spotify=True, blocked=False)
        db.record_snippet(session_id, _make_snippet(tmp_path, state='unrecognized'),
                          played_on_spotify=False, blocked=False)

        data = db.get_analytics()
        assert data['total_snippets'] == 4
        assert data['recognized_count'] == 3
        assert data['unrecognized_count'] == 1
        assert data['recognition_rate'] == 75

    def test_top_artists_ordering(self, db, tmp_path):
        session_id = db.start_session()
        for _ in range(5):
            db.record_snippet(session_id,
                              _make_snippet(tmp_path, artist='Popular Artist', name='Hit'),
                              played_on_spotify=True, blocked=False)
        for _ in range(2):
            db.record_snippet(session_id,
                              _make_snippet(tmp_path, artist='Less Popular', name='Song'),
                              played_on_spotify=True, blocked=False)

        data = db.get_analytics()
        assert len(data['top_artists']) == 2
        assert data['top_artists'][0]['artist'] == 'Popular Artist'
        assert data['top_artists'][0]['count'] == 5
        assert data['top_artists'][1]['artist'] == 'Less Popular'

    def test_top_songs_ordering(self, db, tmp_path):
        session_id = db.start_session()
        for _ in range(3):
            db.record_snippet(session_id,
                              _make_snippet(tmp_path, name='Top Hit', artist='A'),
                              played_on_spotify=True, blocked=False)
        db.record_snippet(session_id,
                          _make_snippet(tmp_path, name='One Timer', artist='B'),
                          played_on_spotify=True, blocked=False)

        data = db.get_analytics()
        assert data['top_songs'][0]['name'] == 'Top Hit'
        assert data['top_songs'][0]['count'] == 3

    def test_by_hour_distribution(self, db, tmp_path):
        session_id = db.start_session()
        # Create a snippet at a specific hour
        ts = datetime(2026, 2, 21, 14, 30, 0)  # 2 PM
        snip = _make_snippet(tmp_path, timestamp=ts)
        db.record_snippet(session_id, snip, played_on_spotify=True, blocked=False)

        data = db.get_analytics()
        assert data['by_hour'][14] == 1
        assert sum(data['by_hour']) == 1

    def test_by_day_distribution(self, db, tmp_path):
        session_id = db.start_session()
        # Feb 21, 2026 is a Saturday -> our index 5
        ts = datetime(2026, 2, 21, 14, 0, 0)
        snip = _make_snippet(tmp_path, timestamp=ts)
        db.record_snippet(session_id, snip, played_on_spotify=True, blocked=False)

        data = db.get_analytics()
        assert data['by_day'][5] == 1  # Saturday
        assert sum(data['by_day']) == 1

    def test_album_art_urls(self, db, tmp_path):
        session_id = db.start_session()
        db.record_snippet(session_id,
                          _make_snippet(tmp_path, album_art_url='https://example.com/a.jpg'),
                          played_on_spotify=True, blocked=False)
        db.record_snippet(session_id,
                          _make_snippet(tmp_path, album_art_url='https://example.com/b.jpg'),
                          played_on_spotify=True, blocked=False)

        data = db.get_analytics()
        assert len(data['album_art_urls']) == 2

    def test_session_data(self, db, tmp_path):
        session_id = db.start_session()
        db.record_snippet(session_id, _make_snippet(tmp_path, state='queued'),
                          played_on_spotify=True, blocked=False)
        db.record_snippet(session_id, _make_snippet(tmp_path, state='unrecognized'),
                          played_on_spotify=False, blocked=False)
        db.end_session(session_id)

        data = db.get_analytics()
        assert len(data['sessions']) == 1
        assert data['sessions'][0]['snippets'] == 2
        assert data['sessions'][0]['recognized'] == 1
        assert data['sessions'][0]['played'] == 1

    def test_session_in_progress(self, db):
        db.start_session()
        data = db.get_analytics()
        assert data['sessions'][0]['duration'] == 'In Progress'

    def test_session_duration_formatting(self, db):
        session_id = db.start_session()
        # Manually set timestamps for predictable duration
        db.conn.execute(
            'UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = ?',
            ('2026-02-21T14:00:00', '2026-02-21T16:30:00', session_id)
        )
        db.conn.commit()

        data = db.get_analytics()
        assert data['sessions'][0]['duration'] == '2h 30m'

    def test_played_count(self, db, tmp_path):
        session_id = db.start_session()
        db.record_snippet(session_id, _make_snippet(tmp_path),
                          played_on_spotify=True, blocked=False)
        db.record_snippet(session_id, _make_snippet(tmp_path),
                          played_on_spotify=False, blocked=True)

        data = db.get_analytics()
        assert data['played_count'] == 1
