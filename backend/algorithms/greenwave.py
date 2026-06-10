from dataclasses import dataclass, field
from typing import List, Tuple
import math


@dataclass
class IntersectionInput:
    intersection_id: int
    sequence_order: int
    distance_from_start: float
    green_time: float
    cycle_length: float


@dataclass
class GreenWaveResult:
    common_cycle: float
    design_speed_mps: float
    offsets: List[dict]
    bandwidth: float
    efficiency: float
    time_space_data: List[dict] = field(default_factory=list)
    band_polygons: List[dict] = field(default_factory=list)


def _compute_bandwidth_for_offsets(
    offsets: List[float],
    greens: List[float],
    travel_times: List[float],
    cycle: float,
) -> float:
    """
    Given fixed offsets (start-of-green in absolute time) for each intersection,
    compute the forward-direction bandwidth.

    A platoon departs intersection 0 at time t0. It arrives at intersection i
    at time t0 + travel_time_i. It passes through green at i iff:
        (t0 + travel_time_i) mod C ∈ [offset_i, offset_i + green_i) mod C

    Equivalently, the valid t0 window for intersection i is:
        t0 mod C ∈ [(offset_i - travel_time_i) mod C,
                     (offset_i - travel_time_i + green_i) mod C)

    Bandwidth = length of intersection of all these circular intervals on [0, C).
    """
    n = len(offsets)
    if n == 0:
        return 0.0
    if n == 1:
        return greens[0]

    # Build circular intervals in t0-space
    intervals: List[Tuple[float, float]] = []
    for i in range(n):
        start = (offsets[i] - travel_times[i]) % cycle
        intervals.append((start, greens[i]))

    return _circular_interval_intersection(intervals, cycle)


def _circular_interval_intersection(
    intervals: List[Tuple[float, float]], cycle: float
) -> float:
    """
    Compute the maximum contiguous overlap of circular intervals on a ring
    of circumference `cycle`. Each interval is (start, length).

    Uses the sweep-from-each-start approach: for each interval start point,
    compute the minimum remaining green across all intervals.
    """
    n = len(intervals)
    if n == 0:
        return 0.0
    if n == 1:
        return min(intervals[0][1], cycle)

    # Critical candidate positions: the start of each interval (on the ring)
    # is where the bandwidth could begin or where a constraint changes.
    # Also check end points (start + length) mod cycle, since an interval
    # dropping off is also a critical transition.
    candidates = set()
    for (s, g) in intervals:
        candidates.add(s % cycle)
        candidates.add((s + g) % cycle)

    best_bw = 0.0
    for cand in candidates:
        min_remaining = cycle
        for (s, g) in intervals:
            s_mod = s % cycle
            # Forward distance from s_mod to cand on the ring
            dist = (cand - s_mod) % cycle
            if dist < g:
                remaining = g - dist
            else:
                remaining = 0.0
            min_remaining = min(min_remaining, remaining)
            if min_remaining == 0.0:
                break
        best_bw = max(best_bw, min_remaining)

    return best_bw


def _optimize_offsets_constrained(
    sorted_ints: List[IntersectionInput],
    speed_mps: float,
    common_cycle: float,
) -> Tuple[List[float], float]:
    """
    Constrained offset search for bandwidth maximization.

    Each intersection has a FIXED green time (from its existing plan).
    The decision variable per intersection is its offset (start-of-green
    within the cycle), constrained to [0, C).

    The first intersection's offset is fixed at 0 (reference).
    For each subsequent intersection, we search over discrete offset values
    to find the combination maximizing forward bandwidth.

    For n intersections, exhaustive search is O(C^(n-1)) which is intractable
    for large n. We use a sequential greedy heuristic with refinement:

    Phase 1 - Travel-time baseline:
        offset_i = travel_time_i mod C  (platoon arrives at green start)

    Phase 2 - Sequential search:
        For each intersection 1..n-1, search offset in [0, C) at 1s resolution
        to maximize bandwidth with all previously fixed offsets.

    Phase 3 - Global refinement:
        Iteratively adjust each offset (holding others fixed) to improve
        total bandwidth. Repeat until no improvement.
    """
    n = len(sorted_ints)
    if n == 0:
        return [], 0.0
    if n == 1:
        return [0.0], sorted_ints[0].green_time

    travel_times = [intx.distance_from_start / speed_mps for intx in sorted_ints]
    greens = [intx.green_time for intx in sorted_ints]

    resolution = 0.5
    steps = int(common_cycle / resolution)

    # Phase 1: baseline offsets from travel time (analytically optimal for
    # uniform greens in the forward direction: platoon arrives at green start)
    offsets = [(travel_times[i]) % common_cycle for i in range(n)]
    offsets[0] = 0.0  # reference

    # Phase 1: baseline offsets from travel time (analytically optimal for
    # uniform greens in the forward direction: platoon arrives at green start)
    offsets = [(travel_times[i]) % common_cycle for i in range(n)]
    offsets[0] = 0.0  # reference

    baseline_bw = _compute_bandwidth_for_offsets(offsets, greens, travel_times, common_cycle)
    baseline_offsets = list(offsets)

    # Phase 2: sequential optimization
    # Fix intersection 0 offset at 0. For each subsequent intersection,
    # find the offset that maximizes bandwidth considering all intersections
    # up to and including the current one.
    # Include the baseline offset as a candidate to guarantee monotonic improvement.
    for target in range(1, n):
        best_bw_local = -1.0
        best_offset_local = offsets[target]

        # Build candidate set: discrete grid + baseline offset for this intersection
        candidate_set = set(step * resolution for step in range(steps))
        candidate_set.add(baseline_offsets[target])

        for candidate_offset in candidate_set:
            offsets[target] = candidate_offset
            bw = _compute_bandwidth_for_offsets(offsets, greens, travel_times, common_cycle)
            if bw > best_bw_local:
                best_bw_local = bw
                best_offset_local = candidate_offset

        offsets[target] = best_offset_local

    # Phase 3: iterative refinement (coordinate descent)
    # Re-optimize each offset while holding others fixed.
    # Repeat until convergence or max iterations.
    for iteration in range(5):
        improved = False
        current_bw = _compute_bandwidth_for_offsets(offsets, greens, travel_times, common_cycle)

        for target in range(1, n):
            best_bw_local = current_bw
            best_offset_local = offsets[target]

            for step in range(steps):
                candidate_offset = step * resolution
                offsets[target] = candidate_offset
                bw = _compute_bandwidth_for_offsets(offsets, greens, travel_times, common_cycle)
                if bw > best_bw_local:
                    best_bw_local = bw
                    best_offset_local = candidate_offset

            if best_bw_local > current_bw:
                offsets[target] = best_offset_local
                current_bw = best_bw_local
                improved = True
            else:
                offsets[target] = best_offset_local

        if not improved:
            break

    final_bw = _compute_bandwidth_for_offsets(offsets, greens, travel_times, common_cycle)

    # Guarantee: never return worse than baseline
    if final_bw < baseline_bw:
        return [round(o, 2) for o in baseline_offsets], round(baseline_bw, 2)

    return [round(o, 2) for o in offsets], round(final_bw, 2)


def _find_band_start(
    offsets_list: List[dict],
    travel_times: List[float],
    bandwidth: float,
    common_cycle: float,
) -> float:
    """Find the t0 value at which the band starts (forward direction)."""
    n = len(offsets_list)
    intervals = []
    for i in range(n):
        start = (offsets_list[i]["offset"] - travel_times[i]) % common_cycle
        intervals.append((start, offsets_list[i]["green_time"]))

    # The band start is a point within the intersection of all intervals.
    # Use the sweep approach: find where all intervals overlap maximally,
    # then pick the start of that overlap region.
    candidates = sorted(set(s % common_cycle for (s, _) in intervals))

    for cand in candidates:
        min_remaining = common_cycle
        for (s, g) in intervals:
            dist = (cand - s) % common_cycle
            if dist < g:
                remaining = g - dist
            else:
                remaining = 0.0
            min_remaining = min(min_remaining, remaining)
        if min_remaining >= bandwidth - 0.5:
            return cand

    return 0.0


def calculate_green_wave(
    intersections: List[IntersectionInput],
    design_speed_kmh: float,
    num_cycles_display: int = 3,
) -> GreenWaveResult:
    if not intersections:
        raise ValueError("At least one intersection required")
    if design_speed_kmh <= 0:
        raise ValueError("Design speed must be > 0")

    speed_mps = design_speed_kmh / 3.6
    common_cycle = max(i.cycle_length for i in intersections)
    sorted_ints = sorted(intersections, key=lambda x: x.distance_from_start)

    optimized_offsets, bandwidth = _optimize_offsets_constrained(
        sorted_ints, speed_mps, common_cycle
    )

    travel_times = [intx.distance_from_start / speed_mps for intx in sorted_ints]

    offsets = []
    for i, intx in enumerate(sorted_ints):
        offsets.append({
            "intersection_id": intx.intersection_id,
            "distance": intx.distance_from_start,
            "travel_time": round(travel_times[i], 2),
            "offset": optimized_offsets[i] if i < len(optimized_offsets) else 0.0,
            "green_time": intx.green_time,
        })

    efficiency = (bandwidth / common_cycle) * 100 if common_cycle > 0 else 0

    # Time-space diagram data: green rectangles
    time_space_data = []
    for o in offsets:
        for k in range(num_cycles_display):
            time_space_data.append({
                "intersection_id": o["intersection_id"],
                "distance": o["distance"],
                "green_start": round(o["offset"] + k * common_cycle, 2),
                "green_end": round(o["offset"] + o["green_time"] + k * common_cycle, 2),
                "cycle_index": k,
            })

    # Band polygons
    band_polygons = []
    if bandwidth > 0:
        band_start_t0 = _find_band_start(offsets, travel_times, bandwidth, common_cycle)

        for k in range(num_cycles_display):
            base = band_start_t0 + k * common_cycle
            upper = []
            lower = []
            for i, o in enumerate(offsets):
                t_arrive = base + travel_times[i]
                upper.append({"x": o["distance"], "y": round(t_arrive, 2)})
                lower.append({"x": o["distance"], "y": round(t_arrive + bandwidth, 2)})
            band_polygons.append({
                "direction": "outbound",
                "cycle": k,
                "upper": upper,
                "lower": lower,
            })

    return GreenWaveResult(
        common_cycle=common_cycle,
        design_speed_mps=round(speed_mps, 2),
        offsets=offsets,
        bandwidth=bandwidth,
        efficiency=round(efficiency, 2),
        time_space_data=time_space_data,
        band_polygons=band_polygons,
    )
