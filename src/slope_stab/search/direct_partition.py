from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from slope_stab.search.common import TIE_TOL, Vector3, clip01


PayloadT = TypeVar("PayloadT")

_SIZE_ROUND = 15
_LIPSCHITZ_POWERS = tuple(range(-6, 7))
_DIMENSIONS = 3


@dataclass(frozen=True)
class DirectRectangle(Generic[PayloadT]):
    rect_id: int
    center: Vector3
    half_sizes: Vector3
    score: float
    payload: PayloadT

    @property
    def size_metric(self) -> float:
        return max(self.half_sizes)


def best_rectangles_per_size(rectangles: list[DirectRectangle[PayloadT]]) -> list[DirectRectangle[PayloadT]]:
    best_by_size: dict[float, DirectRectangle[PayloadT]] = {}
    for rect in rectangles:
        key = round(rect.size_metric, _SIZE_ROUND)
        current = best_by_size.get(key)
        if current is None:
            best_by_size[key] = rect
            continue
        if rect.score < current.score - TIE_TOL:
            best_by_size[key] = rect
            continue
        if abs(rect.score - current.score) <= TIE_TOL and rect.rect_id < current.rect_id:
            best_by_size[key] = rect
    return sorted(best_by_size.values(), key=lambda r: (r.size_metric, r.score, r.rect_id))


def select_potentially_optimal(
    rectangles: list[DirectRectangle[PayloadT]],
    incumbent_id: int | None = None,
) -> list[DirectRectangle[PayloadT]]:
    if not rectangles:
        return []

    reduced = best_rectangles_per_size(rectangles)
    selected: dict[int, DirectRectangle[PayloadT]] = {}

    k_values = [0.0] + [10.0**power for power in _LIPSCHITZ_POWERS]
    for k in k_values:
        chosen = min(
            reduced,
            key=lambda r: (r.score - k * r.size_metric, r.score, r.rect_id),
        )
        selected[chosen.rect_id] = chosen

    if incumbent_id is not None and incumbent_id not in selected:
        incumbent_rect = next((rect for rect in rectangles if rect.rect_id == incumbent_id), None)
        if incumbent_rect is not None:
            selected[incumbent_rect.rect_id] = incumbent_rect

    if not selected:
        fallback = min(rectangles, key=lambda r: (r.score, r.rect_id))
        selected[fallback.rect_id] = fallback

    return sorted(selected.values(), key=lambda r: r.rect_id)


def split_rectangle(
    rectangle: DirectRectangle[PayloadT],
    clip_value: Callable[[float], float] = clip01,
) -> list[tuple[Vector3, Vector3]]:
    half_sizes = rectangle.half_sizes
    max_half = max(half_sizes)
    split_dim = min(
        (i for i in range(_DIMENSIONS) if abs(half_sizes[i] - max_half) <= TIE_TOL),
        default=0,
    )

    delta = half_sizes[split_dim] / 3.0
    new_half_sizes = list(half_sizes)
    new_half_sizes[split_dim] = delta
    child_half_sizes = (new_half_sizes[0], new_half_sizes[1], new_half_sizes[2])

    children: list[tuple[Vector3, Vector3]] = []
    for shift in (-delta, 0.0, delta):
        child_center = list(rectangle.center)
        child_center[split_dim] = clip_value(child_center[split_dim] + shift)
        children.append(((child_center[0], child_center[1], child_center[2]), child_half_sizes))
    return children


def seeded_centers_3x3x3() -> tuple[float, float, float]:
    return (1.0 / 6.0, 0.5, 5.0 / 6.0)
