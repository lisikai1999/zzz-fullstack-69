from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math


@dataclass
class FlowMeasurement:
    phase_number: int
    flow_rate: float


@dataclass
class LibraryPlan:
    plan_id: int
    timing_plan_id: int
    flow_signature: List[float]


@dataclass
class CurrentPlan:
    cycle_length: float
    phase_greens: List[float]
    offset: float


@dataclass
class AdaptiveResult:
    action: str
    selected_plan_id: Optional[int]
    adjustments: Dict[str, float]
    new_cycle: float
    new_greens: List[float]
    new_offset: float
    performance_index: float
    improvement_percent: float


def estimate_delay(cycle: float, green: float, flow: float, saturation: float,
                   proportion_on_green: float = -1.0) -> float:
    """
    HCM-style delay estimation with platoon arrival adjustment.

    d = d1 * PF + d2

    d1 = uniform delay = C*(1-g/C)^2 / (2*(1 - min(1, x)*g/C))
    d2 = incremental (overflow) delay = 900*T*[(x-1) + sqrt((x-1)^2 + 8kIx/(cT))]
         (simplified to 0 for undersaturated conditions: x < 1)
    PF = progression factor = (1 - P) / (1 - g/C)  [capped at 1.0 for unfavorable]

    where:
      x = v/c = flow / (saturation * g/C) = degree of saturation
      P = proportion of vehicles arriving during green (0..1)
      PF adjusts uniform delay based on arrival quality

    If proportion_on_green < 0, assume random arrivals (P = g/C).
    """
    if cycle <= 0 or green <= 0:
        return 9999.0

    lam = green / cycle  # g/C ratio
    capacity = saturation * lam
    x = flow / capacity if capacity > 0 else 1.0  # v/c

    # Uniform delay (d1)
    denom = 2 * (1 - min(x, 1.0) * lam)
    if denom <= 0.01:
        d1 = cycle * 0.5  # cap at half cycle for extreme saturation
    else:
        d1 = cycle * (1 - lam) ** 2 / denom

    # Progression factor
    if proportion_on_green < 0:
        P = lam  # random arrivals: P = g/C
    else:
        P = max(0.0, min(1.0, proportion_on_green))

    if lam >= 1.0:
        PF = 1.0
    else:
        # PF = (1 - P) / (1 - g/C), capped between 0.0 and 1.67
        PF = (1 - P) / (1 - lam)
        PF = max(0.0, min(1.67, PF))

    # Overflow delay (d2) - simplified: only applies when x > 1
    d2 = 0.0
    if x > 1.0:
        T = 0.25  # analysis period in hours (15 min)
        d2 = 900 * T * ((x - 1) + math.sqrt((x - 1) ** 2 + 8 * 0.5 * x / (capacity * T)))

    return d1 * PF + d2


def _platoon_proportion_on_green(
    offset: float, green: float, cycle: float,
    upstream_offset: float, travel_time: float,
    platoon_ratio: float = 0.6,
) -> float:
    """
    Compute the proportion of vehicles arriving on green (P) based on
    platoon arrival distribution.

    Model: a fraction `platoon_ratio` of vehicles arrive as a compact
    platoon; the rest arrive uniformly (random). The platoon arrives at
    a time determined by the upstream signal's offset + travel time.

    platoon_arrival_in_cycle = (upstream_offset + upstream_green_start + travel_time) mod C
    The platoon is "on green" if it arrives within [offset, offset + green) mod C.

    P = platoon_ratio * I(platoon_on_green) + (1 - platoon_ratio) * (g/C)

    where I(platoon_on_green) = 1 if platoon center falls in green window.

    For a more realistic distributed platoon (Robertson dispersion), we compute
    what fraction of the platoon window overlaps with green:
      platoon_duration = 0.2 * C (20% of cycle, typical dispersed platoon)
      platoon_window = [arrival - platoon_duration/2, arrival + platoon_duration/2]
      overlap = intersection of platoon_window and green_window on cycle ring
      P_platoon = overlap / platoon_duration
      P = platoon_ratio * P_platoon + (1 - platoon_ratio) * (g/C)
    """
    lam = green / cycle
    platoon_duration = 0.2 * cycle  # dispersed platoon width

    # Platoon center arrival time within the cycle at this intersection
    platoon_center = (upstream_offset + travel_time) % cycle

    # Compute overlap of platoon window with green window on cycle ring
    # Platoon window: [platoon_center - dur/2, platoon_center + dur/2] mod C
    # Green window: [offset, offset + green] mod C
    platoon_start = (platoon_center - platoon_duration / 2) % cycle
    platoon_end = (platoon_center + platoon_duration / 2) % cycle

    green_start = offset % cycle
    green_end = (offset + green) % cycle

    # Compute circular overlap
    overlap = _circular_overlap(platoon_start, platoon_duration, green_start, green, cycle)
    P_platoon = overlap / platoon_duration if platoon_duration > 0 else lam

    P = platoon_ratio * P_platoon + (1 - platoon_ratio) * lam
    return max(0.0, min(1.0, P))


def _circular_overlap(start_a: float, len_a: float, start_b: float, len_b: float, cycle: float) -> float:
    """Compute overlap length of two intervals on a circle of circumference cycle."""
    # Unwrap: place interval A at [0, len_a] and compute where B falls relative to it.
    # Shift B start relative to A start:
    b_rel = (start_b - start_a) % cycle

    # B occupies [b_rel, b_rel + len_b] on the unwrapped ring from A's perspective
    # A occupies [0, len_a]
    # Overlap = intersection of [0, len_a] and [b_rel, b_rel+len_b] on ring [0, cycle)

    # Direct overlap (no wrapping):
    overlap = max(0.0, min(len_a, b_rel + len_b) - max(0.0, b_rel))

    # Wrapped part: if b_rel + len_b > cycle, the tail wraps to [0, (b_rel+len_b)-cycle]
    if b_rel + len_b > cycle:
        wrap_end = b_rel + len_b - cycle
        overlap += max(0.0, min(len_a, wrap_end))

    return min(overlap, min(len_a, len_b))  # can't exceed either interval's length


def compute_performance_index(
    cycle: float, greens: List[float], flows: List[float], saturations: List[float],
    proportions_on_green: Optional[List[float]] = None,
) -> float:
    """Total weighted delay (performance index to minimize)."""
    pi = 0.0
    for i in range(len(greens)):
        p = proportions_on_green[i] if proportions_on_green else -1.0
        d = estimate_delay(cycle, greens[i], flows[i], saturations[i], p)
        pi += d * flows[i]
    return pi


def select_plan_from_library(
    current_flows: List[FlowMeasurement],
    library: List[LibraryPlan],
) -> Optional[int]:
    if not library or not current_flows:
        return None

    current_vector = [m.flow_rate for m in sorted(current_flows, key=lambda x: x.phase_number)]
    mag = math.sqrt(sum(v ** 2 for v in current_vector))
    if mag == 0:
        return None
    norm_current = [v / mag for v in current_vector]

    best_plan_id = None
    best_similarity = 0.0

    for plan in library:
        if len(plan.flow_signature) != len(norm_current):
            continue
        plan_mag = math.sqrt(sum(v ** 2 for v in plan.flow_signature))
        if plan_mag == 0:
            continue
        dot = sum(a * b for a, b in zip(norm_current, plan.flow_signature))
        similarity = dot / plan_mag
        if similarity > best_similarity:
            best_similarity = similarity
            best_plan_id = plan.timing_plan_id

    return best_plan_id if best_similarity >= 0.8 else None


def scoot_incremental_optimize(
    current_plan: CurrentPlan,
    flows: List[float],
    saturations: List[float],
    min_greens: List[float],
    max_greens: List[float],
    min_cycle: float = 30.0,
    max_cycle: float = 180.0,
    upstream_offset: float = 0.0,
    upstream_green: float = 30.0,
    travel_time_from_upstream: float = 20.0,
    coordinated_phase: int = 0,
    platoon_ratio: float = 0.6,
) -> AdaptiveResult:
    """
    SCOOT-style incremental optimization with platoon-based delay model.

    Additional parameters for coordination delay:
      upstream_offset: start-of-green at the upstream intersection
      upstream_green: green duration at upstream (determines platoon release)
      travel_time_from_upstream: link travel time (seconds)
      coordinated_phase: which phase receives the platoon (index into greens)
      platoon_ratio: fraction of flow in the coordinated platoon (0..1)
    """
    n = len(current_plan.phase_greens)

    # Compute current P (proportion on green) for coordinated phase
    current_P = _platoon_proportion_on_green(
        offset=current_plan.offset,
        green=current_plan.phase_greens[coordinated_phase],
        cycle=current_plan.cycle_length,
        upstream_offset=upstream_offset,
        travel_time=travel_time_from_upstream,
        platoon_ratio=platoon_ratio,
    )
    current_proportions = [
        current_P if i == coordinated_phase else -1.0
        for i in range(n)
    ]

    current_pi = compute_performance_index(
        current_plan.cycle_length, current_plan.phase_greens, flows, saturations,
        current_proportions,
    )

    best_pi = current_pi
    best_adjustment: Dict[str, float] = {}
    best_greens = list(current_plan.phase_greens)
    best_cycle = current_plan.cycle_length
    best_offset = current_plan.offset

    # Split adjustments (evaluate with current coordination state)
    for i in range(n):
        for delta in [4.0, -4.0]:
            candidate = list(current_plan.phase_greens)
            candidate[i] += delta
            if candidate[i] < min_greens[i] or candidate[i] > max_greens[i]:
                continue
            compensation = -delta / (n - 1) if n > 1 else 0
            valid = True
            for j in range(n):
                if j != i:
                    candidate[j] += compensation
                    if candidate[j] < min_greens[j] or candidate[j] > max_greens[j]:
                        valid = False
                        break
            if not valid:
                continue
            # Recompute P if coordinated phase green changed
            split_proportions = list(current_proportions)
            if i == coordinated_phase:
                split_proportions[i] = _platoon_proportion_on_green(
                    offset=current_plan.offset, green=candidate[i], cycle=current_plan.cycle_length,
                    upstream_offset=upstream_offset, travel_time=travel_time_from_upstream,
                    platoon_ratio=platoon_ratio,
                )
            pi = compute_performance_index(
                current_plan.cycle_length, candidate, flows, saturations, split_proportions
            )
            if pi < best_pi:
                best_pi = pi
                best_greens = candidate
                best_cycle = current_plan.cycle_length
                best_adjustment = {f"phase_{i}_green": delta}

    # Cycle adjustments (evaluate with coordination)
    for delta in [4.0, -4.0, 8.0, -8.0]:
        candidate_cycle = current_plan.cycle_length + delta
        if candidate_cycle < min_cycle or candidate_cycle > max_cycle:
            continue
        total_green = sum(current_plan.phase_greens)
        if total_green <= 0:
            continue
        candidate_greens = [g + delta * (g / total_green) for g in current_plan.phase_greens]
        valid = all(
            candidate_greens[i] >= min_greens[i] and candidate_greens[i] <= max_greens[i]
            for i in range(n)
        )
        if not valid:
            continue
        cycle_proportions = list(current_proportions)
        cycle_proportions[coordinated_phase] = _platoon_proportion_on_green(
            offset=current_plan.offset, green=candidate_greens[coordinated_phase],
            cycle=candidate_cycle, upstream_offset=upstream_offset,
            travel_time=travel_time_from_upstream, platoon_ratio=platoon_ratio,
        )
        pi = compute_performance_index(
            candidate_cycle, candidate_greens, flows, saturations, cycle_proportions
        )
        if pi < best_pi:
            best_pi = pi
            best_greens = candidate_greens
            best_cycle = candidate_cycle
            best_adjustment = {"cycle": delta}

    # Offset adjustments
    # Offset changes affect platoon arrival timing at the coordinated phase.
    # Use the platoon dispersion model to compute proportion arriving on green
    # for each candidate offset, then re-evaluate full delay (PI).
    # SCOOT uses ±4s incremental steps; we also evaluate ±8s and an "ideal"
    # candidate (offset aligned to platoon arrival) to escape flat regions.
    ideal_offset = (upstream_offset + travel_time_from_upstream) % best_cycle
    offset_candidates = set()
    for delta in [4.0, -4.0, 8.0, -8.0, 12.0, -12.0]:
        offset_candidates.add(best_offset + delta)
    offset_candidates.add(ideal_offset)
    offset_candidates.add((ideal_offset - best_greens[coordinated_phase] * 0.1) % best_cycle)

    for candidate_offset in offset_candidates:
        candidate_offset = candidate_offset % best_cycle
        candidate_P = _platoon_proportion_on_green(
            offset=candidate_offset,
            green=best_greens[coordinated_phase],
            cycle=best_cycle,
            upstream_offset=upstream_offset,
            travel_time=travel_time_from_upstream,
            platoon_ratio=platoon_ratio,
        )
        candidate_proportions = [
            candidate_P if i == coordinated_phase else -1.0
            for i in range(n)
        ]
        pi = compute_performance_index(
            best_cycle, best_greens, flows, saturations, candidate_proportions
        )
        if pi < best_pi:
            best_pi = pi
            best_offset = candidate_offset
            delta_from_current = (candidate_offset - current_plan.offset + best_cycle / 2) % best_cycle - best_cycle / 2
            best_adjustment = {"offset": round(delta_from_current, 1)}

    improvement = ((current_pi - best_pi) / current_pi * 100) if current_pi > 0 else 0

    return AdaptiveResult(
        action="incremental",
        selected_plan_id=None,
        adjustments=best_adjustment,
        new_cycle=round(best_cycle, 1),
        new_greens=[round(g, 1) for g in best_greens],
        new_offset=round(best_offset, 1),
        performance_index=round(best_pi, 2),
        improvement_percent=round(improvement, 2),
    )
