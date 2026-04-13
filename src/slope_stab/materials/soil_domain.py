from __future__ import annotations

from dataclasses import dataclass
import math

from slope_stab.exceptions import GeometryError
from slope_stab.models import SoilMaterialInput, SoilRegionAssignmentInput, SoilsInput
from slope_stab.surfaces.circular import CircularSlipSurface


Point = tuple[float, float]
Segment = tuple[Point, Point]
_Key = tuple[int, int]


@dataclass(frozen=True)
class GeometryTolerance:
    eps_snap: float
    eps_on_edge: float
    eps_zero_len: float
    eps_zero_area: float
    eps_seed_clearance: float


@dataclass(frozen=True)
class BaseSegmentMaterial:
    material_id: str
    length: float


@dataclass(frozen=True)
class _RawSegment:
    start: Point
    end: Point
    source: str  # "external" | "material"


@dataclass(frozen=True)
class _Face:
    polygon: tuple[Point, ...]
    bbox: tuple[float, float, float, float]
    centroid: Point
    area_abs: float


@dataclass(frozen=True)
class _SplitArrangement:
    coordinates: dict[_Key, Point]
    arrangement_edges: tuple[tuple[_Key, _Key], ...]
    material_segments: tuple[Segment, ...]
    arrangement_segments: tuple[Segment, ...]


class _SnapIndex:
    def __init__(self, step: float) -> None:
        self._step = step
        self._accum: dict[_Key, tuple[float, float, int]] = {}

    def register(self, point: Point) -> _Key:
        x, y = point
        key = (
            int(round(x / self._step)),
            int(round(y / self._step)),
        )
        sx, sy, count = self._accum.get(key, (0.0, 0.0, 0))
        self._accum[key] = (sx + x, sy + y, count + 1)
        return key

    def coordinates(self) -> dict[_Key, Point]:
        coords: dict[_Key, Point] = {}
        for key, (sx, sy, count) in self._accum.items():
            coords[key] = (sx / count, sy / count)
        return coords


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _dot(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * bx + ay * by


def _distance_point_to_segment(point: Point, segment: Segment) -> float:
    (px, py) = point
    (ax, ay), (bx, by) = segment
    abx = bx - ax
    aby = by - ay
    ab2 = _dot(abx, aby, abx, aby)
    if ab2 <= 0.0:
        return math.hypot(px - ax, py - ay)
    t = _dot(px - ax, py - ay, abx, aby) / ab2
    t = min(1.0, max(0.0, t))
    qx = ax + t * abx
    qy = ay + t * aby
    return math.hypot(px - qx, py - qy)


def _point_on_segment(point: Point, segment: Segment, tol: float) -> bool:
    (px, py) = point
    (ax, ay), (bx, by) = segment
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    area2 = abs(_cross(abx, aby, apx, apy))
    scale = max(1.0, abs(abx), abs(aby))
    if area2 > tol * scale:
        return False
    dot = _dot(apx, apy, abx, aby)
    if dot < -tol:
        return False
    ab2 = _dot(abx, aby, abx, aby)
    if dot > ab2 + tol:
        return False
    return True


def _point_in_polygon(point: Point, polygon: tuple[Point, ...], tol: float) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if _point_on_segment(point, ((x1, y1), (x2, y2)), tol):
            return True
        intersects = (y1 > y) != (y2 > y)
        if not intersects:
            continue
        x_hit = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        if x_hit >= x - tol:
            inside = not inside
    return inside


def _point_in_polygon_strict(point: Point, polygon: tuple[Point, ...], tol: float) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        a = polygon[i]
        b = polygon[(i + 1) % n]
        if _point_on_segment(point, (a, b), tol):
            return False
        x1, y1 = a
        x2, y2 = b
        intersects = (y1 > y) != (y2 > y)
        if not intersects:
            continue
        x_hit = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        if x_hit > x:
            inside = not inside
    return inside


def _polygon_signed_area(polygon: tuple[Point, ...]) -> float:
    area2 = 0.0
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        area2 += x1 * y2 - x2 * y1
    return 0.5 * area2


def _polygon_centroid(polygon: tuple[Point, ...], signed_area: float) -> Point:
    if abs(signed_area) <= 0.0:
        sx = sum(x for x, _ in polygon)
        sy = sum(y for _, y in polygon)
        return sx / len(polygon), sy / len(polygon)
    cx_num = 0.0
    cy_num = 0.0
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        cross = x1 * y2 - x2 * y1
        cx_num += (x1 + x2) * cross
        cy_num += (y1 + y2) * cross
    factor = 1.0 / (6.0 * signed_area)
    return cx_num * factor, cy_num * factor


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _segment_intersection_parameters(
    seg_a: Segment,
    seg_b: Segment,
    tol: float,
) -> tuple[float, float] | None:
    (ax, ay), (bx, by) = seg_a
    (cx, cy), (dx, dy) = seg_b
    r_x = bx - ax
    r_y = by - ay
    s_x = dx - cx
    s_y = dy - cy
    denom = _cross(r_x, r_y, s_x, s_y)
    if abs(denom) <= tol:
        return None
    q_p_x = cx - ax
    q_p_y = cy - ay
    t = _cross(q_p_x, q_p_y, s_x, s_y) / denom
    u = _cross(q_p_x, q_p_y, r_x, r_y) / denom
    if -tol <= t <= 1.0 + tol and -tol <= u <= 1.0 + tol:
        return float(t), float(u)
    return None


def _segments_colinear_overlap(seg_a: Segment, seg_b: Segment, tol: float) -> bool:
    (ax, ay), (bx, by) = seg_a
    (cx, cy), (dx, dy) = seg_b
    abx = bx - ax
    aby = by - ay
    if abs(_cross(abx, aby, cx - ax, cy - ay)) > tol:
        return False
    if abs(_cross(abx, aby, dx - ax, dy - ay)) > tol:
        return False

    ax_min = min(ax, bx)
    ax_max = max(ax, bx)
    ay_min = min(ay, by)
    ay_max = max(ay, by)
    bx_min = min(cx, dx)
    bx_max = max(cx, dx)
    by_min = min(cy, dy)
    by_max = max(cy, dy)

    overlap_x = min(ax_max, bx_max) - max(ax_min, bx_min)
    overlap_y = min(ay_max, by_max) - max(ay_min, by_min)
    if max(overlap_x, overlap_y) <= tol:
        return False
    return True


def _dedupe_sorted(values: list[float], eps: float) -> list[float]:
    unique: list[float] = []
    for value in sorted(values):
        if not unique or abs(value - unique[-1]) > eps:
            unique.append(value)
    return unique


def _iter_boundary_segments(polylines: tuple[tuple[Point, ...], ...], eps_zero_len: float) -> list[Segment]:
    segments: list[Segment] = []
    for polyline in polylines:
        for p1, p2 in zip(polyline[:-1], polyline[1:]):
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= eps_zero_len:
                continue
            segments.append((p1, p2))
    return segments


def _derive_tolerance(external: tuple[Point, ...]) -> GeometryTolerance:
    xs = [x for x, _ in external]
    ys = [y for _, y in external]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    eps_snap = max(1e-8, 1e-7 * span)
    eps_on_edge = max(1e-9, 1e-8 * span)
    eps_zero_len = eps_on_edge
    eps_zero_area = max(1e-12, 1e-10 * span * span)
    eps_seed_clearance = 10.0 * eps_on_edge
    return GeometryTolerance(
        eps_snap=eps_snap,
        eps_on_edge=eps_on_edge,
        eps_zero_len=eps_zero_len,
        eps_zero_area=eps_zero_area,
        eps_seed_clearance=eps_seed_clearance,
    )


def _split_segments(raw_segments: tuple[_RawSegment, ...], tol: GeometryTolerance) -> _SplitArrangement:
    if len(raw_segments) == 0:
        raise GeometryError("At least one segment is required for soil domain arrangement.")

    split_params: list[list[float]] = [[0.0, 1.0] for _ in raw_segments]
    for idx_a in range(len(raw_segments)):
        seg_a = (raw_segments[idx_a].start, raw_segments[idx_a].end)
        for idx_b in range(idx_a + 1, len(raw_segments)):
            seg_b = (raw_segments[idx_b].start, raw_segments[idx_b].end)
            if _segments_colinear_overlap(seg_a, seg_b, tol.eps_on_edge):
                raise GeometryError(
                    "Overlapping colinear soil boundaries are not supported in v1 non-uniform geometry."
                )
            params = _segment_intersection_parameters(seg_a, seg_b, tol.eps_on_edge)
            if params is None:
                continue
            ta, tb = params
            split_params[idx_a].append(_clamp01(ta))
            split_params[idx_b].append(_clamp01(tb))

    snap = _SnapIndex(tol.eps_snap)
    arrangement_edges_set: set[tuple[_Key, _Key]] = set()
    material_edges_set: set[tuple[_Key, _Key]] = set()

    for segment, params in zip(raw_segments, split_params):
        t_values = _dedupe_sorted(params, tol.eps_on_edge)
        (x1, y1) = segment.start
        (x2, y2) = segment.end
        dx = x2 - x1
        dy = y2 - y1
        for t_left, t_right in zip(t_values[:-1], t_values[1:]):
            if t_right <= t_left + tol.eps_on_edge:
                continue
            p_left = (x1 + t_left * dx, y1 + t_left * dy)
            p_right = (x1 + t_right * dx, y1 + t_right * dy)
            if math.hypot(p_right[0] - p_left[0], p_right[1] - p_left[1]) <= tol.eps_zero_len:
                continue
            k_left = snap.register(p_left)
            k_right = snap.register(p_right)
            if k_left == k_right:
                continue
            edge_key = (k_left, k_right) if k_left < k_right else (k_right, k_left)
            arrangement_edges_set.add(edge_key)
            if segment.source == "material":
                material_edges_set.add(edge_key)

    coordinates = snap.coordinates()
    arrangement_edges = tuple(sorted(arrangement_edges_set))
    material_segments = tuple((coordinates[a], coordinates[b]) for a, b in sorted(material_edges_set))
    arrangement_segments = tuple((coordinates[a], coordinates[b]) for a, b in arrangement_edges)

    if len(arrangement_edges) == 0:
        raise GeometryError("Soil domain arrangement contains no valid edges after intersection splitting.")

    return _SplitArrangement(
        coordinates=coordinates,
        arrangement_edges=arrangement_edges,
        material_segments=material_segments,
        arrangement_segments=arrangement_segments,
    )


def _build_faces(
    *,
    arrangement: _SplitArrangement,
    external_boundary: tuple[Point, ...],
    tol: GeometryTolerance,
) -> tuple[_Face, ...]:
    adjacency: dict[_Key, list[_Key]] = {}
    for a, b in arrangement.arrangement_edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    outgoing_sorted: dict[_Key, list[_Key]] = {}
    for key, neighbors in adjacency.items():
        x0, y0 = arrangement.coordinates[key]
        outgoing_sorted[key] = sorted(
            neighbors,
            key=lambda n: math.atan2(
                arrangement.coordinates[n][1] - y0,
                arrangement.coordinates[n][0] - x0,
            ),
        )

    directed_edges: list[tuple[_Key, _Key]] = []
    for a, b in arrangement.arrangement_edges:
        directed_edges.append((a, b))
        directed_edges.append((b, a))
    directed_edges.sort()

    visited: set[tuple[_Key, _Key]] = set()
    faces: list[_Face] = []

    max_steps = max(10, 4 * len(directed_edges))

    for start in directed_edges:
        if start in visited:
            continue
        face_keys: list[_Key] = [start[0]]
        a, b = start

        for _ in range(max_steps):
            visited.add((a, b))
            face_keys.append(b)

            neighbors = outgoing_sorted[b]
            try:
                reverse_idx = neighbors.index(a)
            except ValueError as exc:
                raise GeometryError("Invalid soil arrangement connectivity during face traversal.") from exc
            next_key = neighbors[(reverse_idx - 1) % len(neighbors)]
            a, b = b, next_key
            if (a, b) == start:
                break
        else:
            raise GeometryError("Failed to close a soil face during deterministic face traversal.")

        if face_keys[0] != face_keys[-1]:
            continue
        polygon = tuple(arrangement.coordinates[key] for key in face_keys[:-1])
        if len(polygon) < 3:
            continue

        signed_area = _polygon_signed_area(polygon)
        if signed_area <= tol.eps_zero_area:
            continue
        centroid = _polygon_centroid(polygon, signed_area)
        if not _point_in_polygon(centroid, external_boundary, tol.eps_on_edge):
            continue

        xs = [x for x, _ in polygon]
        ys = [y for _, y in polygon]
        faces.append(
            _Face(
                polygon=polygon,
                bbox=(min(xs), max(xs), min(ys), max(ys)),
                centroid=centroid,
                area_abs=abs(signed_area),
            )
        )

    if len(faces) == 0:
        raise GeometryError("Unable to construct bounded soil faces inside external_boundary.")

    return tuple(
        sorted(
            faces,
            key=lambda face: (
                round(face.centroid[0], 12),
                round(face.centroid[1], 12),
                round(face.area_abs, 12),
            ),
        )
    )


def _point_on_any_segment(point: Point, segments: tuple[Segment, ...], tol: float) -> bool:
    for segment in segments:
        if _distance_point_to_segment(point, segment) <= tol:
            return True
    return False


@dataclass(frozen=True)
class SoilDomain:
    materials: dict[str, SoilMaterialInput]
    external_boundary: tuple[Point, ...]
    boundary_polylines: tuple[tuple[Point, ...], ...]
    boundary_segments: tuple[Segment, ...]
    region_assignments: tuple[SoilRegionAssignmentInput, ...]
    tolerance: GeometryTolerance
    faces: tuple[_Face, ...]
    face_material_ids: tuple[str, ...]
    arrangement_segments: tuple[Segment, ...]

    @property
    def is_non_uniform(self) -> bool:
        return len(self.materials) > 1 or len(self.boundary_segments) > 0

    def _candidate_face_indices(self, point: Point, *, strict: bool) -> list[int]:
        x, y = point
        indices: list[int] = []
        tol = self.tolerance.eps_on_edge
        for idx, face in enumerate(self.faces):
            x_min, x_max, y_min, y_max = face.bbox
            if x < x_min - tol or x > x_max + tol or y < y_min - tol or y > y_max + tol:
                continue
            if strict:
                if _point_in_polygon_strict(point, face.polygon, tol):
                    indices.append(idx)
            else:
                if _point_in_polygon(point, face.polygon, tol):
                    indices.append(idx)
        return indices

    def _resolve_material_id_from_face_indices(self, indices: list[int]) -> str | None:
        if len(indices) == 0:
            return None
        material_ids = {self.face_material_ids[idx] for idx in indices}
        if len(material_ids) == 1:
            return self.face_material_ids[indices[0]]
        raise GeometryError("Point lies on ambiguous material boundary between different face assignments.")

    def material_for_point(self, x: float, y: float) -> SoilMaterialInput:
        point = (float(x), float(y))
        tol = self.tolerance

        if not _point_in_polygon(point, self.external_boundary, tol.eps_on_edge):
            raise GeometryError(f"Point ({x}, {y}) is outside soils external_boundary.")

        if len(self.materials) == 1 and len(self.boundary_segments) == 0:
            return next(iter(self.materials.values()))

        strict_indices = self._candidate_face_indices(point, strict=True)
        strict_material_id = self._resolve_material_id_from_face_indices(strict_indices)
        if strict_material_id is not None:
            return self.materials[strict_material_id]

        if _point_on_any_segment(point, self.arrangement_segments, tol.eps_on_edge):
            offsets = (
                (tol.eps_on_edge, 0.0),
                (-tol.eps_on_edge, 0.0),
                (0.0, tol.eps_on_edge),
                (0.0, -tol.eps_on_edge),
            )
            sampled_material_ids: set[str] = set()
            for dx, dy in offsets:
                sample = (point[0] + dx, point[1] + dy)
                if not _point_in_polygon(sample, self.external_boundary, tol.eps_on_edge):
                    continue
                sample_indices = self._candidate_face_indices(sample, strict=True)
                sample_material_id = self._resolve_material_id_from_face_indices(sample_indices)
                if sample_material_id is not None:
                    sampled_material_ids.add(sample_material_id)
            if len(sampled_material_ids) == 1:
                only_id = next(iter(sampled_material_ids))
                return self.materials[only_id]
            if len(sampled_material_ids) > 1:
                raise GeometryError(
                    f"Point ({x}, {y}) lies on ambiguous material boundary between different materials."
                )

        loose_indices = self._candidate_face_indices(point, strict=False)
        loose_material_id = self._resolve_material_id_from_face_indices(loose_indices)
        if loose_material_id is None:
            raise GeometryError(
                f"Unable to resolve soil material for point ({x}, {y}); point does not map to a material face."
            )
        return self.materials[loose_material_id]

    def vertical_material_lengths(
        self,
        *,
        x: float,
        y_bottom: float,
        y_top: float,
    ) -> dict[str, float]:
        if y_top <= y_bottom + self.tolerance.eps_zero_len:
            return {}

        y_points = [float(y_bottom), float(y_top)]
        for (x1, y1), (x2, y2) in self.boundary_segments:
            if abs(x2 - x1) <= self.tolerance.eps_zero_len:
                if abs(x - x1) <= self.tolerance.eps_on_edge:
                    y_low = min(y1, y2)
                    y_high = max(y1, y2)
                    y_points.append(max(y_bottom, y_low))
                    y_points.append(min(y_top, y_high))
                continue

            if x < min(x1, x2) - self.tolerance.eps_on_edge or x > max(x1, x2) + self.tolerance.eps_on_edge:
                continue

            ratio = (x - x1) / (x2 - x1)
            if ratio < -self.tolerance.eps_on_edge or ratio > 1.0 + self.tolerance.eps_on_edge:
                continue
            y_line = y1 + ratio * (y2 - y1)
            if y_bottom - self.tolerance.eps_on_edge <= y_line <= y_top + self.tolerance.eps_on_edge:
                y_points.append(float(y_line))

        unique = _dedupe_sorted(y_points, self.tolerance.eps_on_edge)

        contributions: dict[str, float] = {}
        for y1, y2 in zip(unique[:-1], unique[1:]):
            if y2 <= y1 + self.tolerance.eps_zero_len:
                continue
            y_mid = 0.5 * (y1 + y2)
            material = self.material_for_point(x, y_mid)
            contributions[material.id] = contributions.get(material.id, 0.0) + (y2 - y1)
        return contributions

    def base_boundary_intersection_xs(
        self,
        *,
        surface: CircularSlipSurface,
        x_left: float,
        x_right: float,
    ) -> list[float]:
        roots: list[float] = []
        for (x1, y1), (x2, y2) in self.boundary_segments:
            dx = x2 - x1
            dy = y2 - y1
            a = dx * dx + dy * dy
            if a <= self.tolerance.eps_zero_len:
                continue
            fx = x1 - surface.xc
            fy = y1 - surface.yc
            b = 2.0 * (fx * dx + fy * dy)
            c = fx * fx + fy * fy - surface.r * surface.r
            disc = b * b - 4.0 * a * c
            if disc < -self.tolerance.eps_on_edge:
                continue
            disc = max(disc, 0.0)
            sqrt_disc = math.sqrt(disc)
            for sign in (-1.0, 1.0):
                t = (-b + sign * sqrt_disc) / (2.0 * a)
                if t < -self.tolerance.eps_on_edge or t > 1.0 + self.tolerance.eps_on_edge:
                    continue
                x = x1 + t * dx
                y = y1 + t * dy
                if x < x_left + self.tolerance.eps_on_edge or x > x_right - self.tolerance.eps_on_edge:
                    continue
                if abs(y - surface.y_base(x)) > 5e-6:
                    continue
                roots.append(float(x))

        return _dedupe_sorted(roots, self.tolerance.eps_on_edge)

    def base_material_segments(
        self,
        *,
        x_left: float,
        y_left: float,
        x_right: float,
        y_right: float,
    ) -> list[BaseSegmentMaterial]:
        if x_right <= x_left + self.tolerance.eps_zero_len:
            return []
        chord = ((x_left, y_left), (x_right, y_right))
        split_t = [0.0, 1.0]
        for segment in self.boundary_segments:
            params = _segment_intersection_parameters(chord, segment, self.tolerance.eps_on_edge)
            if params is None:
                continue
            t, u = params
            if t <= self.tolerance.eps_on_edge or t >= 1.0 - self.tolerance.eps_on_edge:
                continue
            if u <= self.tolerance.eps_on_edge or u >= 1.0 - self.tolerance.eps_on_edge:
                continue
            split_t.append(t)

        merged_t = _dedupe_sorted(split_t, self.tolerance.eps_on_edge)

        segments: list[BaseSegmentMaterial] = []
        for t1, t2 in zip(merged_t[:-1], merged_t[1:]):
            if t2 <= t1 + self.tolerance.eps_zero_len:
                continue
            t_mid = 0.5 * (t1 + t2)
            x_mid = x_left + t_mid * (x_right - x_left)
            y_mid = y_left + t_mid * (y_right - y_left)
            material = self.material_for_point(x_mid, y_mid)
            seg_length = math.hypot((x_right - x_left) * (t2 - t1), (y_right - y_left) * (t2 - t1))
            segments.append(BaseSegmentMaterial(material_id=material.id, length=seg_length))
        return segments


def build_soil_domain(soils: SoilsInput) -> SoilDomain:
    if len(soils.materials) == 0:
        raise GeometryError("At least one soils.materials entry is required.")
    if len(soils.external_boundary) < 3:
        raise GeometryError("soils.external_boundary must contain at least three points.")
    if len(soils.region_assignments) == 0:
        raise GeometryError("At least one soils.region_assignments entry is required.")

    materials: dict[str, SoilMaterialInput] = {}
    for material in soils.materials:
        if material.id in materials:
            raise GeometryError(f"Duplicate soils material id: {material.id}")
        materials[material.id] = material

    external = tuple((float(x), float(y)) for x, y in soils.external_boundary)
    tol = _derive_tolerance(external)
    external_area = _polygon_signed_area(external)
    if abs(external_area) <= tol.eps_zero_area:
        raise GeometryError("soils.external_boundary must enclose a non-zero area polygon.")

    boundaries = tuple(tuple((float(x), float(y)) for x, y in line) for line in soils.material_boundaries)

    for line in boundaries:
        if len(line) < 2:
            raise GeometryError("Each soils.material_boundaries polyline must contain at least two points.")
        for point in line:
            if not _point_in_polygon(point, external, tol.eps_on_edge):
                raise GeometryError("soils.material_boundaries must lie within soils.external_boundary.")

    raw_segments: list[_RawSegment] = []

    for p1, p2 in zip(external, external[1:] + external[:1]):
        if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= tol.eps_zero_len:
            continue
        raw_segments.append(_RawSegment(start=p1, end=p2, source="external"))

    for polyline in boundaries:
        for p1, p2 in zip(polyline[:-1], polyline[1:]):
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= tol.eps_zero_len:
                continue
            raw_segments.append(_RawSegment(start=p1, end=p2, source="material"))

    arrangement = _split_segments(tuple(raw_segments), tol)
    faces = _build_faces(arrangement=arrangement, external_boundary=external, tol=tol)

    face_material_ids: list[str | None] = [None for _ in faces]

    for assignment in soils.region_assignments:
        if assignment.material_id not in materials:
            raise GeometryError(
                f"soils.region_assignments material_id '{assignment.material_id}' does not match soils.materials."
            )
        seed = (float(assignment.seed_x), float(assignment.seed_y))
        if not _point_in_polygon(seed, external, tol.eps_on_edge):
            raise GeometryError(
                f"soils.region_assignments seed ({assignment.seed_x}, {assignment.seed_y}) is outside external_boundary."
            )
        if _point_on_any_segment(seed, arrangement.arrangement_segments, tol.eps_seed_clearance):
            raise GeometryError("soils.region_assignments seed points must not lie on or near boundaries.")

        matching_faces = [
            idx
            for idx, face in enumerate(faces)
            if _point_in_polygon_strict(seed, face.polygon, tol.eps_on_edge)
        ]
        if len(matching_faces) != 1:
            raise GeometryError(
                f"soils.region_assignments seed ({assignment.seed_x}, {assignment.seed_y}) does not map to a unique face."
            )

        face_idx = matching_faces[0]
        existing = face_material_ids[face_idx]
        if existing is not None and existing != assignment.material_id:
            raise GeometryError(
                "Conflicting soils.region_assignments map the same face to different materials."
            )
        face_material_ids[face_idx] = assignment.material_id

    for idx, material_id in enumerate(face_material_ids):
        if material_id is None:
            cx, cy = faces[idx].centroid
            raise GeometryError(
                "Incomplete soils.region_assignments: each bounded face needs at least one seed assignment "
                f"(unassigned face near centroid ({cx:.6g}, {cy:.6g}))."
            )

    boundary_segments = tuple(_iter_boundary_segments(boundaries, tol.eps_zero_len))

    return SoilDomain(
        materials=materials,
        external_boundary=external,
        boundary_polylines=boundaries,
        boundary_segments=boundary_segments,
        region_assignments=soils.region_assignments,
        tolerance=tol,
        faces=faces,
        face_material_ids=tuple(material_id for material_id in face_material_ids if material_id is not None),
        arrangement_segments=arrangement.arrangement_segments,
    )
