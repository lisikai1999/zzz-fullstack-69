from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
import aiosqlite

from database import get_db
from algorithms.webster import calculate_webster, PhaseInput, WebsterResult
from algorithms.greenwave import calculate_green_wave, IntersectionInput, GreenWaveResult
from algorithms.adaptive import (
    scoot_incremental_optimize,
    select_plan_from_library,
    CurrentPlan,
    FlowMeasurement,
    LibraryPlan,
    AdaptiveResult,
)

router = APIRouter(tags=["optimization"])


class WebsterResponse(BaseModel):
    optimal_cycle: float
    actual_cycle: float
    total_lost_time: float
    degree_of_saturation: float
    is_oversaturated: bool
    warnings: List[str]
    phases: List[dict]
    saved_plan_id: Optional[int] = None


class GreenWaveResponse(BaseModel):
    common_cycle: float
    design_speed_mps: float
    bandwidth: float
    efficiency: float
    offsets: List[dict]
    time_space_data: List[dict]
    band_polygons: List[dict]


class AdaptiveResponse(BaseModel):
    action: str
    selected_plan_id: Optional[int]
    adjustments: dict
    new_cycle: float
    new_greens: List[float]
    new_offset: float
    performance_index: float
    improvement_percent: float


@router.post("/optimize/webster/{intersection_id}", response_model=WebsterResponse)
async def optimize_webster(intersection_id: int, db: aiosqlite.Connection = Depends(get_db)):
    row = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Intersection not found")

    intx = dict(row)
    cursor = await db.execute(
        "SELECT * FROM phases WHERE intersection_id = ? ORDER BY phase_number", (intersection_id,)
    )
    phases_rows = [dict(r) for r in await cursor.fetchall()]
    if not phases_rows:
        raise HTTPException(400, "No phases defined for this intersection")

    phase_inputs = [
        PhaseInput(
            phase_number=p["phase_number"],
            phase_type=p["phase_type"],
            flow_rate=p["flow_rate"],
            saturation_flow=p["saturation_flow"],
            lost_time=p["lost_time"],
            min_green=p["min_green"],
            max_green=p["max_green"],
        )
        for p in phases_rows
    ]

    result = calculate_webster(
        phase_inputs,
        min_cycle=intx["min_cycle"],
        max_cycle=intx["max_cycle"],
        total_lost_time_override=intx["total_lost_time"],
    )

    # Save as timing plan
    plan_cursor = await db.execute(
        """INSERT INTO timing_plans (intersection_id, plan_name, cycle_length, total_lost_time, method)
           VALUES (?, ?, ?, ?, ?)""",
        (intersection_id, f"Webster优化 C={result.actual_cycle}s", result.actual_cycle, result.total_lost_time, "webster"),
    )
    plan_id = plan_cursor.lastrowid
    for pr in result.phase_results:
        await db.execute(
            "INSERT INTO plan_phases (timing_plan_id, phase_number, green_time) VALUES (?, ?, ?)",
            (plan_id, pr.phase_number, pr.green_time),
        )
    await db.commit()

    return WebsterResponse(
        optimal_cycle=result.optimal_cycle,
        actual_cycle=result.actual_cycle,
        total_lost_time=result.total_lost_time,
        degree_of_saturation=result.degree_of_saturation,
        is_oversaturated=result.is_oversaturated,
        warnings=result.warnings,
        phases=[{"phase_number": pr.phase_number, "flow_ratio": pr.flow_ratio, "green_time": pr.green_time}
                for pr in result.phase_results],
        saved_plan_id=plan_id,
    )


@router.post("/optimize/greenwave/{arterial_id}", response_model=GreenWaveResponse)
async def optimize_greenwave(arterial_id: int, db: aiosqlite.Connection = Depends(get_db)):
    art_row = await (await db.execute("SELECT * FROM arterials WHERE id = ?", (arterial_id,))).fetchone()
    if not art_row:
        raise HTTPException(404, "Arterial not found")

    cursor = await db.execute(
        """SELECT ai.*, i.name FROM arterial_intersections ai
           JOIN intersections i ON i.id = ai.intersection_id
           WHERE ai.arterial_id = ? ORDER BY ai.sequence_order""",
        (arterial_id,),
    )
    art_ints = [dict(r) for r in await cursor.fetchall()]
    if not art_ints:
        raise HTTPException(400, "No intersections in this arterial")

    # Get coordination phase green time and cycle for each intersection
    inputs = []
    for ai in art_ints:
        phase_row = await (await db.execute(
            "SELECT * FROM phases WHERE intersection_id = ? AND phase_number = ?",
            (ai["intersection_id"], ai["phase_for_coordination"]),
        )).fetchone()

        # Get active plan cycle or default
        plan_row = await (await db.execute(
            "SELECT cycle_length FROM timing_plans WHERE intersection_id = ? AND is_active = 1",
            (ai["intersection_id"],),
        )).fetchone()

        green_time = phase_row["max_green"] if phase_row else 30.0
        cycle = plan_row["cycle_length"] if plan_row else 90.0

        # If there's a plan with phase splits, use actual green
        if plan_row:
            pass  # use default
        if phase_row:
            # Estimate green from flow ratio assuming typical split
            green_time = min(green_time, cycle * 0.4)

        inputs.append(IntersectionInput(
            intersection_id=ai["intersection_id"],
            sequence_order=ai["sequence_order"],
            distance_from_start=ai["distance_from_start"],
            green_time=green_time,
            cycle_length=cycle,
        ))

    result = calculate_green_wave(inputs, design_speed_kmh=art_row["design_speed"])

    # Save offsets back to arterial_intersections
    for offset_data in result.offsets:
        await db.execute(
            "UPDATE arterial_intersections SET offset = ? WHERE arterial_id = ? AND intersection_id = ?",
            (offset_data["offset"], arterial_id, offset_data["intersection_id"]),
        )
    await db.commit()

    return GreenWaveResponse(
        common_cycle=result.common_cycle,
        design_speed_mps=result.design_speed_mps,
        bandwidth=result.bandwidth,
        efficiency=result.efficiency,
        offsets=result.offsets,
        time_space_data=result.time_space_data,
        band_polygons=result.band_polygons,
    )


@router.get("/optimize/greenwave/{arterial_id}/diagram", response_model=GreenWaveResponse)
async def get_greenwave_diagram(arterial_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await optimize_greenwave(arterial_id, db)


class AdaptiveRequest(BaseModel):
    mode: str = "scoot"  # "scats" or "scoot"


@router.post("/optimize/adaptive/{intersection_id}", response_model=AdaptiveResponse)
async def optimize_adaptive(
    intersection_id: int, req: AdaptiveRequest, db: aiosqlite.Connection = Depends(get_db)
):
    intx_row = await (await db.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,))).fetchone()
    if not intx_row:
        raise HTTPException(404, "Intersection not found")

    cursor = await db.execute(
        "SELECT * FROM phases WHERE intersection_id = ? ORDER BY phase_number", (intersection_id,)
    )
    phases_rows = [dict(r) for r in await cursor.fetchall()]
    if not phases_rows:
        raise HTTPException(400, "No phases defined")

    flows = [p["flow_rate"] for p in phases_rows]
    saturations = [p["saturation_flow"] for p in phases_rows]
    min_greens = [p["min_green"] for p in phases_rows]
    max_greens = [p["max_green"] for p in phases_rows]

    # Get current active plan
    plan_row = await (await db.execute(
        "SELECT * FROM timing_plans WHERE intersection_id = ? AND is_active = 1", (intersection_id,)
    )).fetchone()

    if plan_row:
        plan_phases_cursor = await db.execute(
            "SELECT green_time FROM plan_phases WHERE timing_plan_id = ? ORDER BY phase_number",
            (plan_row["id"],),
        )
        plan_greens = [r["green_time"] for r in await plan_phases_cursor.fetchall()]
        current_cycle = plan_row["cycle_length"]
    else:
        current_cycle = 90.0
        available = current_cycle - sum(p["lost_time"] for p in phases_rows)
        plan_greens = [available / len(phases_rows)] * len(phases_rows)

    if req.mode == "scats":
        # SCATS: select from library
        lib_cursor = await db.execute(
            "SELECT * FROM adaptive_plan_library WHERE intersection_id = ?", (intersection_id,)
        )
        lib_rows = [dict(r) for r in await lib_cursor.fetchall()]
        library = [
            LibraryPlan(
                plan_id=lr["id"],
                timing_plan_id=lr["timing_plan_id"],
                flow_signature=json.loads(lr["flow_pattern_signature"]) if lr["flow_pattern_signature"] else [],
            )
            for lr in lib_rows
        ]
        measurements = [FlowMeasurement(phase_number=p["phase_number"], flow_rate=p["flow_rate"]) for p in phases_rows]
        selected = select_plan_from_library(measurements, library)

        if selected:
            return AdaptiveResponse(
                action="plan_switch",
                selected_plan_id=selected,
                adjustments={},
                new_cycle=current_cycle,
                new_greens=plan_greens,
                new_offset=0,
                performance_index=0,
                improvement_percent=0,
            )

    # Fall through to SCOOT
    # Look up upstream coordination parameters from arterial membership
    upstream_offset = 0.0
    upstream_green = 30.0
    travel_time_from_upstream = 20.0
    coordinated_phase = 0

    art_membership = await (await db.execute(
        """SELECT ai.*, a.design_speed FROM arterial_intersections ai
           JOIN arterials a ON a.id = ai.arterial_id
           WHERE ai.intersection_id = ? ORDER BY ai.arterial_id LIMIT 1""",
        (intersection_id,),
    )).fetchone()

    if art_membership:
        seq = art_membership["sequence_order"]
        coordinated_phase_num = art_membership["phase_for_coordination"]
        coordinated_phase = next(
            (i for i, p in enumerate(phases_rows) if p["phase_number"] == coordinated_phase_num), 0
        )
        if seq > 0:
            upstream_row = await (await db.execute(
                """SELECT ai.intersection_id, ai.offset, ai.distance_from_start
                   FROM arterial_intersections ai
                   WHERE ai.arterial_id = ? AND ai.sequence_order = ?""",
                (art_membership["arterial_id"], seq - 1),
            )).fetchone()
            if upstream_row:
                upstream_offset = upstream_row["offset"]
                distance = art_membership["distance_from_start"] - upstream_row["distance_from_start"]
                speed_mps = art_membership["design_speed"] / 3.6
                travel_time_from_upstream = distance / speed_mps if speed_mps > 0 else 20.0
                # Get upstream coordinated phase green
                up_phase = await (await db.execute(
                    "SELECT flow_rate, saturation_flow, max_green FROM phases WHERE intersection_id = ? AND phase_number = ?",
                    (upstream_row["intersection_id"], coordinated_phase_num),
                )).fetchone()
                if up_phase:
                    upstream_green = up_phase["max_green"] * 0.4

    current_offset = 0.0
    if art_membership:
        current_offset = art_membership["offset"]

    current = CurrentPlan(cycle_length=current_cycle, phase_greens=plan_greens, offset=current_offset)
    result = scoot_incremental_optimize(
        current, flows, saturations, min_greens, max_greens,
        min_cycle=intx_row["min_cycle"], max_cycle=intx_row["max_cycle"],
        upstream_offset=upstream_offset,
        upstream_green=upstream_green,
        travel_time_from_upstream=travel_time_from_upstream,
        coordinated_phase=coordinated_phase,
        platoon_ratio=0.6,
    )

    return AdaptiveResponse(
        action=result.action,
        selected_plan_id=result.selected_plan_id,
        adjustments=result.adjustments,
        new_cycle=result.new_cycle,
        new_greens=result.new_greens,
        new_offset=result.new_offset,
        performance_index=result.performance_index,
        improvement_percent=result.improvement_percent,
    )
