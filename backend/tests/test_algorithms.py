import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithms.webster import calculate_webster, PhaseInput
from algorithms.greenwave import calculate_green_wave, IntersectionInput
from algorithms.adaptive import scoot_incremental_optimize, CurrentPlan


def test_webster_basic():
    phases = [
        PhaseInput(1, "vehicle", 600, 1800, 3, 7, 60),
        PhaseInput(2, "vehicle", 400, 1800, 3, 7, 60),
    ]
    result = calculate_webster(phases, min_cycle=30, max_cycle=180)
    assert not result.is_oversaturated
    assert 30 <= result.actual_cycle <= 180
    assert result.degree_of_saturation < 1.0
    assert len(result.phase_results) == 2
    total_green = sum(p.green_time for p in result.phase_results)
    assert total_green <= result.actual_cycle
    print(f"Webster basic: C={result.actual_cycle}s, Y={result.degree_of_saturation}")


def test_webster_oversaturated():
    phases = [
        PhaseInput(1, "vehicle", 1700, 1800, 3, 7, 60),
        PhaseInput(2, "vehicle", 1600, 1800, 3, 7, 60),
    ]
    result = calculate_webster(phases, max_cycle=120)
    assert result.is_oversaturated
    assert result.actual_cycle == 120
    print(f"Webster oversaturated: C={result.actual_cycle}s, Y={result.degree_of_saturation}")


def test_webster_pedestrian_min_green():
    phases = [
        PhaseInput(1, "vehicle", 500, 1800, 3, 7, 60),
        PhaseInput(2, "pedestrian", 50, 1200, 3, 15, 40),
    ]
    result = calculate_webster(phases, min_cycle=30, max_cycle=180)
    ped_phase = [p for p in result.phase_results if p.phase_number == 2][0]
    assert ped_phase.green_time >= 15, f"Pedestrian green {ped_phase.green_time} < 15"
    print(f"Webster ped min green: ped_green={ped_phase.green_time}s")


def test_greenwave_basic():
    inputs = [
        IntersectionInput(1, 0, 0, 40, 90),
        IntersectionInput(2, 1, 300, 40, 90),
        IntersectionInput(3, 2, 600, 40, 90),
    ]
    result = calculate_green_wave(inputs, design_speed_kmh=60)
    assert result.common_cycle == 90
    assert len(result.offsets) == 3
    assert result.offsets[0]["offset"] == 0
    assert result.bandwidth >= 0
    print(f"Greenwave: bandwidth={result.bandwidth}s, efficiency={result.efficiency}%")


def test_scoot():
    current = CurrentPlan(cycle_length=90, phase_greens=[20, 25, 30, 15], offset=0)
    flows = [700, 220, 550, 80]
    saturations = [1800, 1600, 1800, 1200]
    result = scoot_incremental_optimize(current, flows, saturations, [7, 5, 7, 15], [60, 40, 60, 40])
    assert result.action == "incremental"
    assert result.performance_index > 0
    print(f"SCOOT: adjustment={result.adjustments}, improvement={result.improvement_percent}%")


if __name__ == "__main__":
    test_webster_basic()
    test_webster_oversaturated()
    test_webster_pedestrian_min_green()
    test_greenwave_basic()
    test_scoot()
    print("\nAll tests passed!")
