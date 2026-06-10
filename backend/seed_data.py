"""Seed demo data: 6 intersections along a main arterial in Chengdu."""
import asyncio
import aiosqlite
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import DB_PATH
from database import init_db


async def seed():
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Check if already seeded
        row = await (await db.execute("SELECT COUNT(*) as c FROM intersections")).fetchone()
        if row[0] > 0:
            print("Database already has data, skipping seed.")
            return

        # Create 6 intersections along a north-south arterial
        intersections = [
            ("人民路/一环路", 30.5700, 104.0650),
            ("人民路/二环路", 30.5740, 104.0650),
            ("人民路/三环路", 30.5780, 104.0650),
            ("人民路/锦江路", 30.5820, 104.0650),
            ("人民路/建设路", 30.5860, 104.0650),
            ("人民路/成华大道", 30.5900, 104.0650),
        ]

        int_ids = []
        for name, lat, lng in intersections:
            cursor = await db.execute(
                "INSERT INTO intersections (name, latitude, longitude, total_lost_time, min_cycle, max_cycle) VALUES (?, ?, ?, 12, 40, 160)",
                (name, lat, lng),
            )
            int_ids.append(cursor.lastrowid)

        # Add 4 phases to each intersection
        phase_templates = [
            (1, "南北直行", "vehicle", 7, 60, 3, 1800),
            (2, "南北左转", "left_turn", 5, 40, 3, 1600),
            (3, "东西直行", "vehicle", 7, 60, 3, 1800),
            (4, "行人过街", "pedestrian", 15, 40, 3, 1200),
        ]
        flow_patterns = [
            [700, 220, 550, 80],
            [650, 200, 600, 90],
            [600, 180, 500, 100],
            [750, 250, 480, 70],
            [580, 190, 520, 110],
            [620, 210, 540, 85],
        ]

        for idx, int_id in enumerate(int_ids):
            for pi, (pnum, pname, ptype, ming, maxg, lost, sat) in enumerate(phase_templates):
                flow = flow_patterns[idx][pi]
                await db.execute(
                    """INSERT INTO phases (intersection_id, phase_number, phase_name, phase_type,
                       min_green, max_green, lost_time, flow_rate, saturation_flow)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (int_id, pnum, pname, ptype, ming, maxg, lost, flow, sat),
                )

        # Add detectors
        approaches = ["NB", "SB", "EB", "WB"]
        for int_id in int_ids:
            for app in approaches:
                await db.execute(
                    "INSERT INTO detectors (intersection_id, detector_name, approach, detector_type) VALUES (?, ?, ?, 'loop')",
                    (int_id, f"{app}检测器", app),
                )

        # Generate flow data for first detector (simulating a day)
        det_cursor = await db.execute("SELECT id FROM detectors LIMIT 1")
        det_row = await det_cursor.fetchone()
        if det_row:
            det_id = det_row[0]
            import random
            random.seed(42)
            for hour in range(24):
                for minute in range(0, 60, 5):
                    ts = f"2024-06-01T{hour:02d}:{minute:02d}:00"
                    # Peak hours: 7-9, 17-19
                    base = 40
                    if 7 <= hour <= 9 or 17 <= hour <= 19:
                        base = 90
                    elif 10 <= hour <= 16:
                        base = 60
                    elif 0 <= hour <= 5:
                        base = 15
                    vol = base + random.randint(-10, 15)
                    speed = max(20, 50 - vol * 0.2 + random.uniform(-5, 5))
                    occ = min(95, vol * 0.5 + random.uniform(0, 10))
                    await db.execute(
                        "INSERT INTO flow_data (detector_id, timestamp, volume, occupancy, speed) VALUES (?, ?, ?, ?, ?)",
                        (det_id, ts, vol, round(occ, 1), round(speed, 1)),
                    )

        # Create an arterial
        cursor = await db.execute(
            "INSERT INTO arterials (name, design_speed) VALUES (?, ?)",
            ("人民路干线", 50),
        )
        art_id = cursor.lastrowid

        # Add intersections to arterial (spacing ~400m between each)
        for idx, int_id in enumerate(int_ids):
            await db.execute(
                """INSERT INTO arterial_intersections
                   (arterial_id, intersection_id, sequence_order, distance_from_start, phase_for_coordination)
                   VALUES (?, ?, ?, ?, 1)""",
                (art_id, int_id, idx, idx * 400),
            )

        # Create adaptive plan library for intersection 1
        # Represent different TOD (time-of-day) patterns: morning peak, evening peak, off-peak, night
        int1_id = int_ids[0]
        plan_library = [
            {
                "plan_name": "早高峰方案",
                "cycle": 140,
                "greens": [55, 20, 45, 20],
                "flow_signature": [0.55, 0.17, 0.43, 0.06],  # normalized high NB flow
            },
            {
                "plan_name": "晚高峰方案",
                "cycle": 130,
                "greens": [45, 25, 40, 20],
                "flow_signature": [0.45, 0.22, 0.50, 0.07],  # normalized high EB flow
            },
            {
                "plan_name": "平峰方案",
                "cycle": 90,
                "greens": [30, 15, 28, 17],
                "flow_signature": [0.40, 0.15, 0.38, 0.08],  # balanced moderate flow
            },
            {
                "plan_name": "夜间方案",
                "cycle": 60,
                "greens": [20, 10, 18, 12],
                "flow_signature": [0.30, 0.10, 0.25, 0.12],  # low flow
            },
        ]

        for idx_plan, lib_entry in enumerate(plan_library):
            # Create the actual timing plan
            plan_cursor = await db.execute(
                """INSERT INTO timing_plans (intersection_id, plan_name, cycle_length, total_lost_time, method)
                   VALUES (?, ?, ?, 12, 'adaptive')""",
                (int1_id, lib_entry["plan_name"], lib_entry["cycle"]),
            )
            tp_id = plan_cursor.lastrowid
            for pi, g in enumerate(lib_entry["greens"]):
                await db.execute(
                    "INSERT INTO plan_phases (timing_plan_id, phase_number, green_time) VALUES (?, ?, ?)",
                    (tp_id, pi + 1, g),
                )
            # Add to adaptive library
            import json as json_mod
            await db.execute(
                """INSERT INTO adaptive_plan_library
                   (intersection_id, plan_index, flow_pattern_signature, timing_plan_id, match_score_threshold)
                   VALUES (?, ?, ?, ?, 0.8)""",
                (int1_id, idx_plan, json_mod.dumps(lib_entry["flow_signature"]), tp_id),
            )

        await db.commit()
        print(f"Seeded {len(int_ids)} intersections, 1 arterial, detectors, flow data, and {len(plan_library)} adaptive plans.")


if __name__ == "__main__":
    asyncio.run(seed())
