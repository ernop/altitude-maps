from __future__ import annotations

import re
from pathlib import Path


def replace_name_in_json(json_path: Path, region_id: str, new_name: str) -> bool:
    try:
        text = json_path.read_text(encoding="utf-8")
        # Replace the first occurrence of the name after the specific region_id
        pattern = rf'(\"region_id\":\"{re.escape(region_id)}\".*?\"name\":\")[^\"]+'
        new_text, n = re.subn(pattern, rf"\1{new_name}", text, count=1)
        if n == 0:
            return False
        json_path.write_text(new_text, encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> int:
    base = Path("generated/regions")
    changes = [
        (base / "peninsula_srtm_30m_2048px_v2.json", "peninsula", "San Mateo"),
        (base / "san_mateo_srtm_30m_2048px_v2.json", "san_mateo", "Peninsula"),
    ]

    any_failed = False
    for path, region_id, new_name in changes:
        ok = replace_name_in_json(path, region_id, new_name)
        print(f"Updated {path.name}: {'OK' if ok else 'NOT FOUND'}")
        if not ok:
            any_failed = True

    return 0 if not any_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())


