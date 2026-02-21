"""SQLite persistence layer for analytics data.

Stores snippet processing results and session metadata so the
/analytics dashboard can show real historical data across app restarts.
"""

import os
import sqlite3
from datetime import datetime


class AnalyticsDB:
    """SQLite data access layer for analytics.

    Thread-safe: uses check_same_thread=False and WAL journal mode,
    which allows concurrent reads from Flask threads while the main
    loop thread writes.
    """

    def __init__(self, db_path='data/silent_disco.db'):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      TEXT    NOT NULL,
                ended_at        TEXT,
                snippet_count   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS snippets (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        INTEGER NOT NULL,
                timestamp         TEXT    NOT NULL,
                state             TEXT    NOT NULL,
                track_string      TEXT,
                song_name         TEXT,
                song_artist       TEXT,
                song_id           TEXT,
                album_art_url     TEXT,
                duration_ms       INTEGER,
                played_on_spotify INTEGER NOT NULL DEFAULT 0,
                blocked           INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_snippets_session
                ON snippets(session_id);
            CREATE INDEX IF NOT EXISTS idx_snippets_timestamp
                ON snippets(timestamp);
            CREATE INDEX IF NOT EXISTS idx_snippets_artist
                ON snippets(song_artist);
        ''')

    def start_session(self):
        """Start a new listening session. Returns the session ID."""
        cur = self.conn.execute(
            'INSERT INTO sessions (started_at) VALUES (?)',
            (datetime.now().isoformat(),)
        )
        self.conn.commit()
        return cur.lastrowid

    def end_session(self, session_id):
        """End a session, setting ended_at and final snippet_count."""
        count = self.conn.execute(
            'SELECT COUNT(*) FROM snippets WHERE session_id = ?',
            (session_id,)
        ).fetchone()[0]
        self.conn.execute(
            'UPDATE sessions SET ended_at = ?, snippet_count = ? WHERE id = ?',
            (datetime.now().isoformat(), count, session_id)
        )
        self.conn.commit()

    def record_snippet(self, session_id, snippet, played_on_spotify, blocked):
        """Record a processed snippet to the database."""
        self.conn.execute(
            '''INSERT INTO snippets
               (session_id, timestamp, state, track_string,
                song_name, song_artist, song_id, album_art_url,
                duration_ms, played_on_spotify, blocked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                session_id,
                snippet.timestamp.isoformat(),
                snippet.state.value,
                snippet.track_string,
                snippet.song_name,
                snippet.song_artist,
                snippet.song_id,
                snippet.album_art_url,
                snippet.duration_ms,
                1 if played_on_spotify else 0,
                1 if blocked else 0,
            )
        )
        self.conn.commit()

    def get_analytics(self):
        """Return all analytics data for the dashboard."""
        c = self.conn

        # Summary counts
        row = c.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN state IN ('recognized','queueable','queued') THEN 1 ELSE 0 END) as recognized,
                SUM(CASE WHEN state = 'unrecognized' THEN 1 ELSE 0 END) as unrecognized,
                SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN played_on_spotify = 1 THEN 1 ELSE 0 END) as played
            FROM snippets
        ''').fetchone()

        total = row['total']
        recognized = row['recognized'] or 0
        unrecognized = row['unrecognized'] or 0
        failed = row['failed'] or 0
        played = row['played'] or 0
        rate = round(recognized / total * 100) if total > 0 else 0

        session_count = c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]

        # Top artists
        top_artists = [
            {'artist': r['song_artist'], 'count': r['cnt']}
            for r in c.execute('''
                SELECT song_artist, COUNT(*) as cnt
                FROM snippets WHERE song_artist IS NOT NULL
                GROUP BY song_artist ORDER BY cnt DESC LIMIT 10
            ''')
        ]

        # Top songs
        top_songs = [
            {'name': r['song_name'], 'artist': r['song_artist'],
             'album_art_url': r['album_art_url'], 'count': r['cnt']}
            for r in c.execute('''
                SELECT song_name, song_artist, album_art_url, COUNT(*) as cnt
                FROM snippets WHERE song_name IS NOT NULL
                GROUP BY song_name, song_artist ORDER BY cnt DESC LIMIT 10
            ''')
        ]

        # By hour (24 buckets)
        by_hour = [0] * 24
        for r in c.execute('''
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, COUNT(*) as cnt
            FROM snippets GROUP BY hour
        '''):
            by_hour[r['hour']] = r['cnt']

        # By day of week (Mon=0 .. Sun=6)
        # SQLite %w: 0=Sunday, 1=Monday ... 6=Saturday
        by_day = [0] * 7
        for r in c.execute('''
            SELECT CAST(strftime('%w', timestamp) AS INTEGER) as dow, COUNT(*) as cnt
            FROM snippets GROUP BY dow
        '''):
            # Remap: SQLite Sunday=0 -> our index 6, Monday=1 -> 0, etc.
            idx = (r['dow'] - 1) % 7
            by_day[idx] = r['cnt']

        # Album art wall (unique, most recent first)
        album_art_urls = [
            r[0]
            for r in c.execute('''
                SELECT album_art_url, MAX(timestamp) as latest
                FROM snippets
                WHERE album_art_url IS NOT NULL
                GROUP BY album_art_url
                ORDER BY latest DESC
                LIMIT 20
            ''').fetchall()
        ]

        # Sessions
        sessions = []
        for r in c.execute('''
            SELECT s.id, s.started_at, s.ended_at, s.snippet_count,
                   (SELECT COUNT(*) FROM snippets
                    WHERE session_id = s.id
                    AND state IN ('recognized','queueable','queued')) as recognized,
                   (SELECT COUNT(*) FROM snippets
                    WHERE session_id = s.id
                    AND played_on_spotify = 1) as played
            FROM sessions s ORDER BY s.started_at DESC LIMIT 20
        '''):
            started = datetime.fromisoformat(r['started_at'])
            if r['ended_at']:
                ended = datetime.fromisoformat(r['ended_at'])
                dur_seconds = int((ended - started).total_seconds())
                hours, remainder = divmod(dur_seconds, 3600)
                minutes = remainder // 60
                duration = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            else:
                duration = "In Progress"

            sessions.append({
                'date': started.strftime('%b %d, %Y %I:%M %p'),
                'duration': duration,
                'snippets': r['snippet_count'],
                'recognized': r['recognized'] or 0,
                'played': r['played'] or 0,
            })

        return {
            'total_snippets': total,
            'recognized_count': recognized,
            'unrecognized_count': unrecognized,
            'failed_count': failed,
            'played_count': played,
            'session_count': session_count,
            'recognition_rate': rate,
            'top_artists': top_artists,
            'top_songs': top_songs,
            'by_hour': by_hour,
            'by_day': by_day,
            'album_art_urls': album_art_urls,
            'sessions': sessions,
        }

    def close(self):
        """Close the database connection."""
        self.conn.close()
