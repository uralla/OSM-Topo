from pathlib import Path
import re

p = Path('uralla_build/preprocessor.py')
s = p.read_text(encoding='utf-8')

patterns = [
    (r"\n    solnyshko_accommodation_sample: dict\[str, object\] \| None = None\n", "\n", 1),
    (r"\n                    if \(\n                        accommodation_sample is not None\n                        and accommodation_sample\.get\(\"name\"\) == \"Солнышко\"\n                    \):\n                        solnyshko_accommodation_sample = dict\(accommodation_sample\)\n", "\n", 1),
    (r"\n                    if \(\n                        activity_sample is not None\n                        and activity_sample\.get\(\"name\"\) == \"Солнышко\"\n                        and solnyshko_accommodation_sample is not None\n                        and activity_sample\.get\(\"id\"\) == solnyshko_accommodation_sample\.get\(\"id\"\)\n                    \):\n                        solnyshko_accommodation_sample\[\"activity_500m\"\] = activity_sample\[\"activity_500m\"\]\n                        solnyshko_accommodation_sample\[\"activity_2km\"\] = activity_sample\[\"activity_2km\"\]\n                        solnyshko_accommodation_sample\[\"activity_10km\"\] = activity_sample\[\"activity_10km\"\]\n                        solnyshko_accommodation_sample\[\"screen_pressure_2km\"\] = activity_sample\[\"screen_pressure_2km\"\]\n                        solnyshko_accommodation_sample\[\"screen_pressure_10km\"\] = activity_sample\[\"screen_pressure_10km\"\]\n                        solnyshko_accommodation_sample\[\"screen_pressure\"\] = activity_sample\[\"screen_pressure\"\]\n", "\n", 1),
    (r"\n            if solnyshko_accommodation_sample is not None:\n                _emit_progress\(\n                    \"POI screen pressure named check: 'Солнышко'; \"\n                    f\"id=\{solnyshko_accommodation_sample\.get\('id'\)\}; \"\n                    f\"priority=\{solnyshko_accommodation_sample\.get\('priority'\)\}; \"\n                    f\"2km=\{solnyshko_accommodation_sample\.get\('screen_pressure_2km'\)\}; \"\n                    f\"10km=\{solnyshko_accommodation_sample\.get\('screen_pressure_10km'\)\}; \"\n                    f\"pressure=\{solnyshko_accommodation_sample\.get\('screen_pressure'\)\}; \"\n                    f\"activity2km=\{solnyshko_accommodation_sample\.get\('activity_2km'\)\}; \"\n                    f\"activity10km=\{solnyshko_accommodation_sample\.get\('activity_10km'\)\}\"\n                \)\n", "\n", 1),
    (r"\n        if solnyshko_accommodation_sample is None:\n            _emit_progress\(\"POI accommodation check: 'Солнышко' not enriched\"\)\n        else:\n            _emit_progress\(\n                \"POI accommodation check: \"\n                f\"'Солнышко'; id=\{solnyshko_accommodation_sample\['id'\]\}; \"\n                f\"lat=\{float\(solnyshko_accommodation_sample\['lat'\]\):\.6f\}; \"\n                f\"lon=\{float\(solnyshko_accommodation_sample\['lon'\]\):\.6f\}; \"\n                f\"2km=\{solnyshko_accommodation_sample\['objects_2km'\]\}; \"\n                f\"10km=\{solnyshko_accommodation_sample\['objects_10km'\]\}; \"\n                f\"activity500m=\{solnyshko_accommodation_sample\.get\('activity_500m', 'n/a'\)\}; \"\n                f\"activity2km=\{solnyshko_accommodation_sample\.get\('activity_2km', 'n/a'\)\}; \"\n                f\"activity10km=\{solnyshko_accommodation_sample\.get\('activity_10km', 'n/a'\)\}; \"\n                f\"activity_context=\{classify_activity_context\(activity_2km=int\(solnyshko_accommodation_sample\.get\('activity_2km', 0\)\), activity_10km=int\(solnyshko_accommodation_sample\.get\('activity_10km', 0\)\), local_p25=activity_2km_p25, local_p75=activity_2km_p75, background_p25=activity_10km_p25, background_p75=activity_10km_p75\) if activity_500m_values else 'n/a'\}; \"\n                f\"priority=\{solnyshko_accommodation_sample\['priority'\]\}\"\n            \)\n", "\n", 1),
]

for pattern, replacement, expected in patterns:
    s, count = re.subn(pattern, replacement, s, count=expected)
    if count != expected:
        raise SystemExit(f'expected {expected} match for pattern, got {count}: {pattern[:100]}')

if 'Солнышко' in s or 'solnyshko_' in s.lower():
    raise SystemExit('Solnyshko diagnostic residue remains in preprocessor.py')

p.write_text(s, encoding='utf-8')

for path in (
    Path('.github/workflows/debug-solnyshko-accommodation.yml'),
    Path('.github/workflows/debug-solnyshko-neighbors.yml'),
):
    if not path.exists():
        raise SystemExit(f'missing expected debug workflow: {path}')
    path.unlink()
