#!/usr/bin/env python3
"""树莓社 B 站视频数据更新脚本（2026-10-19 验证可用的方案）。

## 背景：为什么这么写
B 站对 `x/space/wbi/arc/search`（UP 主视频列表 API）是重风控桶：
纯 API 调用（curl_cffi Chrome TLS 指纹 / bili_ticket / dm_img 参数）均返回
-352 风控校验失败。实测可用的链路是「SPA 页面 + 公开 API」两条弱风控路径：

  第一步（列表）：用真实 Chromium 打开 UP 主空间投稿页，从 DOM 收集 BV 号
    （页面自身会带上正确的 wbi 签名和 cookie 请求 arc/search）。
    注意：新版 fresh-space 分页按钮是 .vui_pagenation--btn / .vui_pagenation--item，
    列表不在 window 滚动容器里；同一会话请求过频会被限流（列表变空），需换新会话。
  第二步（详情）：对每个 BV 调 /x/web-interface/view（弱风控，匿名可用），
    拿 title/aid/cid/pic/pubdate/duration/desc/stat。

## 用法
  1. 浏览器收集最新视频 BV 列表（playwright-cli，见 collect 命令注释），
     结果保存为 bilibili_crawl_raw.json（BV 号数组）。
  2. 运行本脚本：python3 crawl_bilibili.py update
     - 与 works.csv 比对找新增视频
     - view API 补详情、下载封面到 covers/
     - 追加 works.csv 新行（分类按标题关键词猜测，需人工复核）
     - 合并更新 bilibili_videos.json / bilibili_videos.csv
     - 把本次新增写入 works_new_videos.csv（暂存记录）
  3. 运行 python3 sync_works_fallback.py 同步 index.html 内置备份
"""

import csv
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MID = "275501702"  # 树莓社
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CST = timezone(timedelta(hours=8))

WORKS_CSV = ROOT / "works.csv"
JSON_PATH = ROOT / "bilibili_videos.json"
CSV_PATH = ROOT / "bilibili_videos.csv"
STAGING_PATH = ROOT / "works_new_videos.csv"
COVERS_DIR = ROOT / "covers"
RAW_LIST = ROOT / "bilibili_crawl_raw.json"  # 第一步收集到的 BV 列表


def http_get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Referer": "https://www.bilibili.com/"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_view(bvid: str) -> dict:
    """view API：匿名可用，弱风控。"""
    d = http_get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    if d.get("code") != 0:
        raise RuntimeError(f"{bvid} view API: {d.get('code')} {d.get('message')}")
    return d["data"]


def download_cover(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    path = COVERS_DIR / name
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Referer": "https://www.bilibili.com/"})
        with urllib.request.urlopen(req, timeout=20) as resp, open(path, "wb") as f:
            f.write(resp.read())
        print(f"  封面已下载: {name}")
    return f"covers/{name}"


def guess_category(title: str) -> tuple[str, str]:
    rules = [
        (("舞蹈", "Dynamite", "宅舞"), ("dance", "舞蹈表演")),
        (("好声音", "歌曲", "音乐", "合唱", "主题歌", "十佳歌手", "唱"), ("music", "音乐现场")),
        (("采访", "预热", "新闻", "播报", "周报", "预告"), ("news", "校园新闻")),
        (("运动会", "排球", "足球", "篮球", "羽毛球", "乒乓", "体育", "越野"), ("sports", "体育赛事")),
        (("辩论", "微电影", "短片", "纪录", "心理剧", "原创影片"), ("original", "原创作品")),
        (("典礼", "大赛", "决赛", "集锦", "活动", "开学", "军训", "比赛", "收官", "开幕"),
         ("events", "校园活动")),
    ]
    for keys, cat in rules:
        for k in keys:
            if k in title:
                return cat
    return ("events", "校园活动")


def fmt_duration(sec: int) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def collect() -> None:
    """第一步：用 playwright-cli 从空间页收集 BV 列表，存为 bilibili_crawl_raw.json。

    实测命令（2026-10-19，匿名 Chromium 即可过风控）：
      playwright-cli open "https://space.bilibili.com/275501702/upload/video"
      playwright-cli run-code "async page => { ... }"   # 收集 a[href*='/video/BV']
    翻页按钮：.vui_pagenation--btn（下一页）/ .vui_pagenation--item（页码）。
    被限流时列表会变空，需 playwright-cli close 后重开会话。
    """
    print("请按 docstring 中的 collect 说明用 playwright-cli 收集 BV 列表，")
    print("或直接编辑 bilibili_crawl_raw.json 后运行: python3 crawl_bilibili.py update")


def update() -> None:
    if not RAW_LIST.exists():
        raise SystemExit(f"缺少 {RAW_LIST.name}，先收集 BV 列表")
    crawled: list[str] = json.loads(RAW_LIST.read_text(encoding="utf-8"))
    print(f"本次收集到 {len(crawled)} 个 BV")

    works_rows = list(csv.DictReader(open(WORKS_CSV, encoding="utf-8-sig")))
    known = set()
    for r in works_rows:
        if "bvid=" in (r.get("bilibiliSrc") or ""):
            known.add(r["bilibiliSrc"].split("bvid=")[1].split("&")[0])
    new_bvs = [b for b in crawled if b not in known]
    print(f"works.csv 已有 {len(known)} 个，新增 {len(new_bvs)} 个: {new_bvs}")

    old_json = json.loads(JSON_PATH.read_text(encoding="utf-8")) if JSON_PATH.exists() else {}
    entries: list[dict] = []
    for bvid in new_bvs:
        v = fetch_view(bvid)
        pub = datetime.fromtimestamp(v["pubdate"], CST)
        entry = {
            "bvid": bvid,
            "aid": v["aid"],
            "cid": v["cid"],
            "title": v["title"],
            "desc": v.get("desc", ""),
            "pic": v["pic"],
            "duration": v["duration"],
            "pubdate": v["pubdate"],
            "owner": {"mid": int(MID), "name": v["owner"]["name"]},
            "search": {
                "title": v["title"],
                "duration": fmt_duration(v["duration"]),
                "play": v["stat"]["view"],
                "pubdate": v["pubdate"],
            },
        }
        print(f"  + {bvid} | {pub:%Y-%m-%d} | {v['title']} | 播放 {v['stat']['view']}")
        entries.append(entry)
        time.sleep(1.0)  # 温柔一点

    if not entries:
        print("没有新增视频，无需更新")
        return

    # 封面下载
    for e in entries:
        e["local_cover"] = download_cover(e["pic"])

    # 合并 bilibili_videos.json / csv
    merged = dict(old_json)
    for e in entries:
        merged[e["bvid"]] = e
    ordered = dict(sorted(merged.items(), key=lambda kv: -kv[1]["pubdate"]))
    JSON_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["bvid", "aid", "cid", "title", "cover", "duration_sec",
                    "duration_text", "pubdate", "play", "bilibiliSrc", "desc"])
        for e in ordered.values():
            d = datetime.fromtimestamp(e["pubdate"], CST)
            w.writerow([e["bvid"], e["aid"], e["cid"] or "", e["title"],
                        e.get("local_cover", e["pic"]), e["duration"] or "",
                        e["search"]["duration"], d.strftime("%Y-%m-%d"),
                        e["search"]["play"],
                        f"//player.bilibili.com/player.html?isOutside=true&aid={e['aid']}&bvid={e['bvid']}&cid={e['cid'] or ''}&p=1",
                        e["desc"]])
    print(f"bilibili_videos.json/csv 已更新（{len(ordered)} 条）")

    # 追加 works.csv 新行（分类为关键词猜测，需人工复核）
    max_id = max(int(r["id"]) for r in works_rows if r.get("id", "").isdigit())
    new_rows = []
    with open(WORKS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for e in sorted(entries, key=lambda x: x["pubdate"]):
            max_id += 1
            cat, catname = guess_category(e["title"])
            pub = datetime.fromtimestamp(e["pubdate"], CST)
            row = [max_id, "video", cat, catname, e["title"], e["local_cover"],
                   f"//player.bilibili.com/player.html?isOutside=true&aid={e['aid']}&bvid={e['bvid']}&cid={e['cid']}&p=1",
                   "", pub.strftime("%Y年%-m月%-d日"), e["search"]["duration"],
                   e["desc"], "", ""]
            w.writerow(row)
            new_rows.append(dict(zip(["id", "type", "category", "categoryName", "title",
                                      "cover", "bilibiliSrc", "audioSrc", "episodeDate",
                                      "duration", "desc", "activity", "credits"], row)))
            print(f"  works.csv 追加 id={max_id} [{cat}/{catname}] {e['title']}")

    # 暂存文件记录本次新增（沿用既有约定）
    with open(STAGING_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "type", "category", "categoryName", "title",
                                          "cover", "bilibiliSrc", "audioSrc", "episodeDate",
                                          "duration", "desc", "activity", "credits"])
        w.writeheader()
        w.writerows(new_rows)
    print(f"works_new_videos.csv 已更新（{len(new_rows)} 条暂存）")
    print("完成。请运行: python3 sync_works_fallback.py 同步 index.html")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "collect":
        collect()
    elif cmd == "update":
        update()
    else:
        raise SystemExit("用法: crawl_bilibili.py [collect|update]")
