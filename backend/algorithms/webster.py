from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PhaseInput:
    phase_number: int
    phase_type: str
    flow_rate: float
    saturation_flow: float
    lost_time: float
    min_green: float
    max_green: float


@dataclass
class PhaseResult:
    phase_number: int
    flow_ratio: float
    green_time: float


@dataclass
class WebsterResult:
    optimal_cycle: float
    actual_cycle: float
    total_lost_time: float
    degree_of_saturation: float
    phase_results: List[PhaseResult]
    is_oversaturated: bool
    warnings: List[str] = field(default_factory=list)


def calculate_webster(
    phases: List[PhaseInput],
    min_cycle: float = 30.0,
    max_cycle: float = 180.0,
    total_lost_time_override: Optional[float] = None,
) -> WebsterResult:
    if not phases:
        raise ValueError("At least one phase required")

    warnings: List[str] = []

    flow_ratios = []
    for p in phases:
        if p.saturation_flow <= 0:
            raise ValueError(f"Phase {p.phase_number}: saturation_flow must be > 0")
        flow_ratios.append(p.flow_rate / p.saturation_flow)

    Y = sum(flow_ratios)
    L = total_lost_time_override if total_lost_time_override is not None else sum(p.lost_time for p in phases)

    is_oversaturated = Y >= 1.0
    if is_oversaturated:
        warnings.append(f"路口过饱和 (Y={Y:.3f} >= 1.0)，使用最大周期")
        C0 = max_cycle
        C = max_cycle
    else:
        C0 = (1.5 * L + 5) / (1 - Y)
        C = max(min_cycle, min(max_cycle, C0))
        if abs(C - C0) > 0.5:
            warnings.append(f"周期从 {C0:.1f}s 约束至 {C:.1f}s")

    available_green = C - L
    if available_green < 0:
        available_green = 0
        warnings.append("可用绿灯时间不足，请检查损失时间设置")

    if Y > 0:
        green_times = [fr / Y * available_green for fr in flow_ratios]
    else:
        green_times = [available_green / len(phases)] * len(phases)

    for _iteration in range(10):
        adjusted = False
        deficit = 0.0
        flexible_indices = []

        for i, p in enumerate(phases):
            if green_times[i] < p.min_green:
                deficit += p.min_green - green_times[i]
                green_times[i] = p.min_green
                adjusted = True
            elif green_times[i] > p.max_green:
                deficit -= green_times[i] - p.max_green
                green_times[i] = p.max_green
                adjusted = True
            else:
                flexible_indices.append(i)

        if not adjusted or not flexible_indices:
            break

        flex_total = sum(green_times[i] for i in flexible_indices)
        if flex_total > 0:
            for i in flexible_indices:
                green_times[i] -= deficit * (green_times[i] / flex_total)

    phase_results = [
        PhaseResult(
            phase_number=phases[i].phase_number,
            flow_ratio=round(flow_ratios[i], 4),
            green_time=round(green_times[i], 1),
        )
        for i in range(len(phases))
    ]

    return WebsterResult(
        optimal_cycle=round(C0, 1),
        actual_cycle=round(C, 1),
        total_lost_time=round(L, 1),
        degree_of_saturation=round(Y, 4),
        phase_results=phase_results,
        is_oversaturated=is_oversaturated,
        warnings=warnings,
    )
