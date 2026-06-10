from fastapi import APIRouter, Depends, HTTPException
import aiosqlite

from database import get_db
from models.intersection import IntersectionCreate, IntersectionUpdate, IntersectionOut

router = APIRouter(tags=["intersections"])


@router.get("/intersections", response_model=list[IntersectionOut])
async def list_intersections(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM intersections ORDER BY id")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("/intersections", response_model=IntersectionOut, status_code=201)
async def create_intersection(data: IntersectionCreate, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """INSERT INTO intersections (name, latitude, longitude, intersection_type, total_lost_time, min_cycle, max_cycle)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data.name, data.latitude, data.longitude, data.intersection_type,
         data.total_lost_time, data.min_cycle, data.max_cycle),
    )
    await db.commit()
    row = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (cursor.lastrowid,))).fetchone()
    return dict(row)


@router.get("/intersections/{intersection_id}", response_model=IntersectionOut)
async def get_intersection(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    row = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Intersection not found")
    return dict(row)


@router.put("/intersections/{intersection_id}", response_model=IntersectionOut)
async def update_intersection(intersection_id: int, data: IntersectionUpdate, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Intersection not found")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [intersection_id]
        await db.execute(f"UPDATE intersections SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
        await db.commit()
    row = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    return dict(row)


@router.delete("/intersections/{intersection_id}", status_code=204)
async def delete_intersection(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    existing = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not existing:
        raise HTTPException(404, "Intersection not found")
    await db.execute("DELETE FROM intersections WHERE id = ?", (intersection_id,))
    await db.commit()
