#!/usr/bin/env python3
"""把 works.csv 同步为 index.html 里的 FALLBACK_CSV（works.csv 修改后运行一次）。"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "works.csv"
HTML_PATH = ROOT / "index.html"

MARKER = "const FALLBACK_CSV = "

def main() -> None:
    csv_text = CSV_PATH.read_text(encoding="utf-8")
    escaped = json.dumps(csv_text, ensure_ascii=False)

    html = HTML_PATH.read_text(encoding="utf-8")
    lines = html.splitlines(keepends=True)
    replaced = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(MARKER):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = indent + MARKER + escaped + ";\n"
            replaced = True
            break
    if not replaced:
        raise SystemExit("未找到 FALLBACK_CSV 行，请检查 index.html")
    HTML_PATH.write_text(encoding="utf-8", data="".join(lines))
    print(f"FALLBACK_CSV 已更新（{len(escaped)} 字符）")

if __name__ == "__main__":
    main()
