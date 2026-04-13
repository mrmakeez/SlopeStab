from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Scenario:
    name: str
    rfcreport_relpath: str
    s01_relpath: str


SCENARIOS = (
    Scenario(
        name="case11",
        rfcreport_relpath="Verification/Bishop/Case 11/Case11/Case11-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 11/Case11/{BC8DAACB-0FC5-4533-9DBF-C3A02BF591C3}.s01",
    ),
    Scenario(
        name="case11_water_seismic_surcharge",
        rfcreport_relpath=(
            "Verification/Bishop/Case 11/Case11_Water_Seismic_Surcharge/Case11_Water_Seismic_Surcharge-i.rfcreport"
        ),
        s01_relpath=(
            "Verification/Bishop/Case 11/Case11_Water_Seismic_Surcharge/{BC8DAACB-0FC5-4533-9DBF-C3A02BF591C3}.s01"
        ),
    ),
    Scenario(
        name="case12",
        rfcreport_relpath="Verification/Bishop/Case 12/Case12/Case12-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 12/Case12/{1037F11D-9D57-4d8e-9382-344BCEA71DA7}.s01",
    ),
    Scenario(
        name="case12_water_surcharge",
        rfcreport_relpath="Verification/Bishop/Case 12/Case12_Water_Surcharge/Case12_Water_Surcharge-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 12/Case12_Water_Surcharge/{1037F11D-9D57-4d8e-9382-344BCEA71DA7}.s01",
    ),
)


def _parse_rfcreport_methods(text: str) -> dict[str, dict[str, float]]:
    start = text.find("<Title>Global Minimum</Title>")
    fragment = text[start if start != -1 else 0 :]
    results: dict[str, dict[str, float]] = {}
    for match in re.finditer(r"<Title>Method: ([^<]+)</Title>(.*?)</rfc_section>", fragment, re.S):
        method = match.group(1).strip().lower()
        block = match.group(2)

        def _extract(label: str) -> str | None:
            hit = re.search(
                rf"<data_string>{re.escape(label)}</data_string>\s*<data_string>([^<]+)</data_string>",
                block,
            )
            return hit.group(1).strip() if hit else None

        fs = _extract("FS")
        center = _extract("Center:")
        radius = _extract("Radius:")
        left = _extract("Left Slip Surface Endpoint:")
        right = _extract("Right Slip Surface Endpoint:")
        if fs is None or center is None or radius is None or left is None or right is None:
            continue
        xc, yc = [float(part.strip()) for part in center.split(",")]
        xl, yl = [float(part.strip()) for part in left.split(",")]
        xr, yr = [float(part.strip()) for part in right.split(",")]
        results[method] = {
            "fos": float(fs),
            "xc": xc,
            "yc": yc,
            "r": float(radius),
            "x_left": xl,
            "y_left": yl,
            "x_right": xr,
            "y_right": yr,
        }
        if len(results) == 2:
            break
    return results


def _parse_s01_global_minima(text: str) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    start = text.find("* Global Minimum FS")
    if start == -1:
        return results
    for raw in text[start:].splitlines()[1:]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*"):
            break
        parts = line.split()
        if len(parts) < 9:
            continue
        method = " ".join(parts[8:]).lower()
        results[method] = {
            "xc": float(parts[0]),
            "yc": float(parts[1]),
            "r": float(parts[2]),
            "x_left": float(parts[3]),
            "y_left": float(parts[4]),
            "x_right": float(parts[5]),
            "y_right": float(parts[6]),
            "fos": float(parts[7]),
        }
    return results


def build_manifest() -> dict[str, object]:
    scenarios_payload: dict[str, object] = {}
    for scenario in SCENARIOS:
        rfcreport_path = REPO_ROOT / scenario.rfcreport_relpath
        s01_path = REPO_ROOT / scenario.s01_relpath
        rfcreport_methods = _parse_rfcreport_methods(rfcreport_path.read_text(encoding="utf-8", errors="ignore"))
        s01_methods = _parse_s01_global_minima(s01_path.read_text(encoding="utf-8", errors="ignore"))

        agreements: dict[str, dict[str, float | bool]] = {}
        for method, rfcreport_data in rfcreport_methods.items():
            s01_data = s01_methods.get(method)
            if s01_data is None:
                continue
            agreements[method] = {
                "fos_abs_delta": abs(rfcreport_data["fos"] - s01_data["fos"]),
                "center_abs_delta": max(
                    abs(rfcreport_data["xc"] - s01_data["xc"]),
                    abs(rfcreport_data["yc"] - s01_data["yc"]),
                ),
                "radius_abs_delta": abs(rfcreport_data["r"] - s01_data["r"]),
                "left_abs_delta": max(
                    abs(rfcreport_data["x_left"] - s01_data["x_left"]),
                    abs(rfcreport_data["y_left"] - s01_data["y_left"]),
                ),
                "right_abs_delta": max(
                    abs(rfcreport_data["x_right"] - s01_data["x_right"]),
                    abs(rfcreport_data["y_right"] - s01_data["y_right"]),
                ),
                "pass_fos_1e6": abs(rfcreport_data["fos"] - s01_data["fos"]) <= 1e-6,
                "pass_geometry_1e5": (
                    max(
                        abs(rfcreport_data["xc"] - s01_data["xc"]),
                        abs(rfcreport_data["yc"] - s01_data["yc"]),
                        abs(rfcreport_data["r"] - s01_data["r"]),
                        abs(rfcreport_data["x_left"] - s01_data["x_left"]),
                        abs(rfcreport_data["y_left"] - s01_data["y_left"]),
                        abs(rfcreport_data["x_right"] - s01_data["x_right"]),
                        abs(rfcreport_data["y_right"] - s01_data["y_right"]),
                    )
                    <= 1e-5
                ),
            }

        scenarios_payload[scenario.name] = {
            "sources": {
                "rfcreport": scenario.rfcreport_relpath,
                "s01": scenario.s01_relpath,
            },
            "rfcreport_methods": rfcreport_methods,
            "s01_methods": s01_methods,
            "agreements": agreements,
        }

    return {"scenarios": scenarios_payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Case 11/12 verification-oracle manifest and source-agreement deltas."
    )
    parser.add_argument(
        "--output",
        default="tmp/case11_case12_manifest.json",
        help="Output JSON path (relative to repo root).",
    )
    args = parser.parse_args()

    payload = build_manifest()
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote manifest: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
