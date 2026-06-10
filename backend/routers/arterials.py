from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.arterial import ArterialCreate, ArterialUpdate, ArterialOut, ArterialDetail

router = APIRouter(tags=["arterials"])


@router.get("/arterials", response_model=list[ArterialOut])
async def list_arterials(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM arterials ORDER BY id")
    return [dict(row) for row in await cursor.fetchall()]


@router.post("/arterials", response_model=ArterialDetail, status_code=201)
async def create_arterial(data: ArterialCreate, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "INSERT INTO arterials (name, design_speed) VALUES (?, ?)",
        (data.name, data.design_speed),
    )
    arterial_id = cursor.lastrowid
    for item in data.intersections:
        await db.execute(
            """INSERT INTO arterial_intersections
               (arterial_id, intersection_id, sequence_order, distance_from_start, phase_for_coordination)
               VALUES (?, ?, ?, ?, ?)""",
            (arterial_id, item["intersection_id"], item["sequence_order"],
             item["distance_from_start"], item.get("phase_for_coordination", 1)),
        )
    await db.commit()
    return await _get_arterial_detail(arterial_id, db)


@router.get("/arterials/{arterial_id}", response_model=ArterialDetail)
async def get_arterial(arterial_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await _get_arterial_detail(arterial_id, db)


@router.put("/arterials/{arterial_id}", response_model=ArterialOut)
async def update_arterial(arterial_id: int, data: ArterialUpdate, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT id FROM arterials WHERE id = ?", (arterial_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Arterial not found")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [arterial_id]
        await db.execute(f"UPDATE arterials SET {set_clause} WHERE id = ?", values)
        await db.commit()
    row = await (await db.execute("SELECT * FROM arterials WHERE id = ?", (arterial_id,))).fetchone()
    return dict(row)


@router.delete("/arterials/{arterial_id}", status_code=204)
async def delete_arterial(arterial_id: int, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT id FROM arterials WHERE id = ?", (arterial_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Arterial not found")
    await db.execute("DELETE FROM arterials WHERE id = ?", (arterial_id,))
    await db.commit()


async def _get_arterial_detail(arterial_id: int, db: aiosqlite.Connection) -> dict:
    row = await (await db.execute("SELECT * FROM arterials WHERE id = ?", (arterial_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Arterial not found")
    result = dict(row)
    cursor = await db.execute(
        """SELECT ai.intersection_id, ai.sequence_order, ai.distance_from_start,
                  ai.phase_for_coordination, ai.offset, i.name
           FROM arterial_intersections ai
           JOIN intersections i ON i.id = ai.intersection_id
           WHERE ai.arterial_id = ? ORDER BY ai.sequence_order""",
        (arterial_id,),
    )
    result["intersections"] = [dict(r) for r in await cursor.fetchall()]
    return result
