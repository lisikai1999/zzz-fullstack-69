import aiosqlite
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS intersections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    intersection_type TEXT DEFAULT 'signalized',
    total_lost_time REAL DEFAULT 12.0,
    min_cycle REAL DEFAULT 30.0,
    max_cycle REAL DEFAULT 180.0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL,
    phase_name TEXT,
    phase_type TEXT DEFAULT 'vehicle',
    min_green REAL DEFAULT 7.0,
    max_green REAL DEFAULT 60.0,
    yellow_time REAL DEFAULT 3.0,
    all_red_time REAL DEFAULT 2.0,
    lost_time REAL DEFAULT 3.0,
    flow_rate REAL DEFAULT 0.0,
    saturation_flow REAL DEFAULT 1800.0,
    UNIQUE(intersection_id, phase_number)
);

CREATE TABLE IF NOT EXISTS detectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    detector_name TEXT,
    approach TEXT,
    lane_number INTEGER DEFAULT 1,
    detector_type TEXT DEFAULT 'loop'
);

CREATE TABLE IF NOT EXISTS flow_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detector_id INTEGER NOT NULL REFERENCES detectors(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    volume INTEGER NOT NULL,
    occupancy REAL,
    speed REAL,
    interval_seconds INTEGER DEFAULT 300
);

CREATE TABLE IF NOT EXISTS timing_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    plan_name TEXT,
    cycle_length REAL NOT NULL,
    total_lost_time REAL,
    is_active INTEGER DEFAULT 0,
    method TEXT DEFAULT 'webster',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timing_plan_id INTEGER NOT NULL REFERENCES timing_plans(id) ON DELETE CASCADE,
    phase_number INTEGER NOT NULL,
    green_time REAL NOT NULL,
    offset REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS arterials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    design_speed REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS arterial_intersections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arterial_id INTEGER NOT NULL REFERENCES arterials(id) ON DELETE CASCADE,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,
    distance_from_start REAL NOT NULL,
    phase_for_coordination INTEGER NOT NULL DEFAULT 1,
    offset REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS adaptive_plan_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    plan_index INTEGER NOT NULL,
    flow_pattern_signature TEXT,
    timing_plan_id INTEGER REFERENCES timing_plans(id),
    match_score_threshold REAL DEFAULT 0.8
);

CREATE INDEX IF NOT EXISTS idx_flow_data_detector_time ON flow_data(detector_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_phases_intersection ON phases(intersection_id);
CREATE INDEX IF NOT EXISTS idx_arterial_intersections ON arterial_intersections(arterial_id, sequence_order);
"""


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
