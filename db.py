"""
freewispr database layer — SQLite storage for meetings and transcript segments.

Schema:
  meetings  — one row per recording session
  segments  — timestamped lines belonging to a meeting
  segments_fts — full-text search index over segment text
"""
import sqlite3
import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path.home() / ".freewispr" / "freewispr.db"


def init():
    """Create tables if they don't exist. Safe to call on every launch."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS meetings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      TEXT    NOT NULL,
                ended_at        TEXT,
                duration_sec    REAL,
                has_system_audio INTEGER DEFAULT 0,
                summary         TEXT
            );

            CREATE TABLE IF NOT EXISTS segments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id  INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                start_sec   REAL    NOT NULL,
                end_sec     REAL,
                text        TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_seg_meeting ON segments(meeting_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS segments_fts
                USING fts5(text, content=segments, content_rowid=id);

            CREATE TRIGGER IF NOT EXISTS seg_ai AFTER INSERT ON segments BEGIN
                INSERT INTO segments_fts(rowid, text) VALUES (new.id, new.text);
            END;

            CREATE TRIGGER IF NOT EXISTS seg_ad AFTER DELETE ON segments BEGIN
                INSERT INTO segments_fts(segments_fts, rowid, text)
                    VALUES ('delete', old.id, old.text);
            END;
        """)


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# --------------------------------------------------------------------------- #
#  Write                                                                       #
# --------------------------------------------------------------------------- #

def start_meeting(has_system_audio: bool = False) -> int:
    """Insert a new meeting row and return its id."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO meetings (started_at, has_system_audio) VALUES (?, ?)",
            (now, int(has_system_audio)),
        )
        return cur.lastrowid


def end_meeting(meeting_id: int, duration_sec: float):
    """Mark a meeting as finished."""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "UPDATE meetings SET ended_at=?, duration_sec=? WHERE id=?",
            (now, round(duration_sec, 1), meeting_id),
        )


def add_segment(meeting_id: int, start_sec: float, end_sec: float, text: str):
    """Append a transcript segment to the database."""
    with _conn() as con:
        con.execute(
            "INSERT INTO segments (meeting_id, start_sec, end_sec, text) VALUES (?,?,?,?)",
            (meeting_id, start_sec, end_sec, text.strip()),
        )


def save_summary(meeting_id: int, summary: str):
    with _conn() as con:
        con.execute(
            "UPDATE meetings SET summary=? WHERE id=?",
            (summary.strip(), meeting_id),
        )


# --------------------------------------------------------------------------- #
#  Read                                                                        #
# --------------------------------------------------------------------------- #

def get_meetings(limit: int = 100) -> list[dict]:
    """Return recent meetings newest-first."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT m.id, m.started_at, m.ended_at, m.duration_sec,
                   m.has_system_audio, m.summary,
                   (SELECT text FROM segments WHERE meeting_id=m.id
                    ORDER BY start_sec LIMIT 1) AS preview
            FROM meetings m
            ORDER BY m.started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_segments(meeting_id: int) -> list[dict]:
    """Return all segments for a meeting ordered by time."""
    with _conn() as con:
        rows = con.execute(
            "SELECT start_sec, end_sec, text FROM segments WHERE meeting_id=? ORDER BY start_sec",
            (meeting_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def search(query: str, limit: int = 50) -> list[dict]:
    """
    Full-text search across all transcript segments.
    Returns rows with meeting context.
    """
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.meeting_id, s.start_sec, s.text,
                   m.started_at
            FROM segments_fts f
            JOIN segments s ON s.id = f.rowid
            JOIN meetings m ON m.id = s.meeting_id
            WHERE segments_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_meeting(meeting_id: int):
    with _conn() as con:
        con.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def fmt_duration(sec: float | None) -> str:
    if sec is None:
        return "—"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(iso)
        return dt.strftime("%b %d, %Y  %H:%M")
    except Exception:
        return iso
