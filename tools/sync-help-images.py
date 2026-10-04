#!/usr/bin/env python3
"""Copy the help screenshots named in tools/help-images.json from homepage/img into the apps
(Ubuntu: linux/data/help, Android: app assets help/) and write an index.json next to them:
{"entry title": [{"light": "file.webp", "dark": "file.webp" | null}, …]}. homepage/img stays the
only source; run this after new screenshots (tools/demo-screenshots-ubuntu.py, MarketingShots)."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "homepage" / "img"
TARGETS = {"ubuntu": ROOT / "linux" / "data" / "help", "android": ROOT / "android" / "app" / "src" / "main" / "assets" / "help"}


def dark_name(name):
    platform, _sep, rest = name.partition("-")
    return f"{platform}-dark-{rest}"


def main():
    mapping = json.loads((ROOT / "tools" / "help-images.json").read_text())
    for platform, target in TARGETS.items():
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        index = {}
        for title, names in mapping[platform].items():
            pictures = []
            for name in names:
                entry = {"light": f"{name}.webp", "dark": None}
                shutil.copy2(SOURCE / entry["light"], target / entry["light"])
                if (SOURCE / f"{dark_name(name)}.webp").exists():
                    entry["dark"] = f"{dark_name(name)}.webp"
                    shutil.copy2(SOURCE / entry["dark"], target / entry["dark"])
                pictures.append(entry)
            index[title] = pictures
        (target / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n")
        size = sum(f.stat().st_size for f in target.iterdir())
        print(f"{platform}: {len(index)} Einträge, {len(list(target.glob('*.webp')))} Bilder, {size // 1024} KB → {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
