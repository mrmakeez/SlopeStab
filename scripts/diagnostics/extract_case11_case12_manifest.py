from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DEFAULT = "src/slope_stab/verification/data/case11_case12_slide2_manifest.json"
FOS_AGREEMENT_TOLERANCE = 1e-6
_METHOD_NAME_MAP = {
    "bishop simplified": "bishop_simplified",
    "spencer": "spencer",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    rfcreport_relpath: str
    s01_relpath: str


SCENARIOS = (
    Scenario(
        name="Case11",
        rfcreport_relpath="Verification/Bishop/Case 11/Case11/Case11-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 11/Case11/{BC8DAACB-0FC5-4533-9DBF-C3A02BF591C3}.s01",
    ),
    Scenario(
        name="Case11_Water_Seismic_Surcharge",
        rfcreport_relpath=(
            "Verification/Bishop/Case 11/Case11_Water_Seismic_Surcharge/Case11_Water_Seismic_Surcharge-i.rfcreport"
        ),
        s01_relpath=(
            "Verification/Bishop/Case 11/Case11_Water_Seismic_Surcharge/{BC8DAACB-0FC5-4533-9DBF-C3A02BF591C3}.s01"
        ),
    ),
    Scenario(
        name="Case12",
        rfcreport_relpath="Verification/Bishop/Case 12/Case12/Case12-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 12/Case12/{1037F11D-9D57-4d8e-9382-344BCEA71DA7}.s01",
    ),
    Scenario(
        name="Case12_Water_Surcharge",
        rfcreport_relpath="Verification/Bishop/Case 12/Case12_Water_Surcharge/Case12_Water_Surcharge-i.rfcreport",
        s01_relpath="Verification/Bishop/Case 12/Case12_Water_Surcharge/{1037F11D-9D57-4d8e-9382-344BCEA71DA7}.s01",
    ),
)


def _normalize_method_name(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized not in _METHOD_NAME_MAP:
        raise ValueError(f"Unsupported Slide2 method label: {raw}")
    return _METHOD_NAME_MAP[normalized]


def _parse_rfcreport_methods(text: str) -> dict[str, dict[str, object]]:
    start = text.find("<Title>Global Minimum</Title>")
    fragment = text[start if start != -1 else 0 :]
    results: dict[str, dict[str, object]] = {}
    for match in re.finditer(r"<Title>Method: ([^<]+)</Title>(.*?)</rfc_section>", fragment, re.S):
        method = _normalize_method_name(match.group(1))
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
            "surface": {
                "xc": xc,
                "yc": yc,
                "r": float(radius),
                "x_left": xl,
                "y_left": yl,
                "x_right": xr,
                "y_right": yr,
            },
        }
    return results


def _parse_s01_global_minima(text: str) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
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
        method = _normalize_method_name(" ".join(parts[8:]))
        results[method] = {
            "fos": float(parts[7]),
            "surface": {
                "xc": float(parts[0]),
                "yc": float(parts[1]),
                "r": float(parts[2]),
                "x_left": float(parts[3]),
                "y_left": float(parts[4]),
                "x_right": float(parts[5]),
                "y_right": float(parts[6]),
            },
        }
    return results


def build_manifest() -> dict[str, object]:
    scenarios_payload: dict[str, object] = {}
    for scenario in SCENARIOS:
        rfcreport_path = REPO_ROOT / scenario.rfcreport_relpath
        s01_path = REPO_ROOT / scenario.s01_relpath
        rfcreport_methods = _parse_rfcreport_methods(rfcreport_path.read_text(encoding="utf-8", errors="ignore"))
        s01_methods = _parse_s01_global_minima(s01_path.read_text(encoding="utf-8", errors="ignore"))

        methods_payload: dict[str, object] = {}
        for method in ("bishop_simplified", "spencer"):
            if method not in rfcreport_methods:
                raise ValueError(f"Missing {method} rfcreport data for {scenario.name}.")
            if method not in s01_methods:
                raise ValueError(f"Missing {method} s01 data for {scenario.name}.")
            fos_abs_delta = abs(float(rfcreport_methods[method]["fos"]) - float(s01_methods[method]["fos"]))
            pass_fos = fos_abs_delta <= FOS_AGREEMENT_TOLERANCE
            methods_payload[method] = {
                "rfcreport": rfcreport_methods[method],
                "s01": s01_methods[method],
                "agreement": {
                    "fos_abs_delta": fos_abs_delta,
                    "pass_fos_1e6": pass_fos,
                },
            }
            if not pass_fos:
                raise ValueError(
                    f"FOS source agreement failed for {scenario.name} / {method}: delta={fos_abs_delta}"
                )

        scenarios_payload[scenario.name] = {
            "sources": {
                "rfcreport": scenario.rfcreport_relpath,
                "s01": scenario.s01_relpath,
            },
            "methods": methods_payload,
        }

    return {"scenarios": scenarios_payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract the committed Case 11/12 Slide2 FOS oracle manifest with source-agreement checks."
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DEFAULT,
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
