#!/usr/bin/env python3
"""
IndexNow 알림 — 새로 생기거나 바뀐 칼럼 주소만 골라 검색엔진에 "새 글 있어요" 하고 알려요.
(IndexNow에 참여하는 빙·네이버·얀덱스 등이 함께 받아요. 구글은 참여하지 않아서 사이트맵으로 알려요.)

  python scripts/indexnow.py plan  → (배포 전) 지금 공개된 사이트와 새로 만든 _site 를 비교해 바뀐 주소를 적어 둠
  python scripts/indexnow.py send  → (배포 후) 적어 둔 주소를 검색엔진에 알림

site.yml 의 indexnow_enabled 가 true 일 때만 실제로 보내요. (정식 오픈 전에는 꺼 둠)
"""
import json
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENDPOINTS = ["https://api.indexnow.org/indexnow", "https://searchadvisor.naver.com/indexnow"]


PLAN = ROOT / ".indexnow-plan.json"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    site = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    base = site["base_url"].rstrip("/")
    new = json.loads((ROOT / "_site" / "published.json").read_text(encoding="utf-8"))["urls"]

    if mode == "send":
        return send(site, base, json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else [])

    try:  # 지금 공개된 사이트의 목록
        with urllib.request.urlopen(base + "/published.json", timeout=15) as r:
            old = json.loads(r.read().decode("utf-8")).get("urls", {})
    except Exception as e:
        print(f"공개된 목록을 못 읽었어요({e}). 전부 새 글로 보고 알릴게요.")
        old = {}

    changed = [u for u, h in new.items() if old.get(u) != h]
    print(f"알릴 주소 {len(changed)}개")
    for u in changed:
        print("  -", u)
    PLAN.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")


def send(site, base, changed):
    if not changed:
        print("알릴 주소가 없어요.")
        return
    if not site.get("indexnow_enabled"):
        print(f"※ {len(changed)}개를 보내지 않았어요 — site.yml 의 indexnow_enabled 가 false (정식 오픈 전).")
        return
    host = base.split("://", 1)[1]
    body = json.dumps({
        "host": host,
        "key": site["indexnow_key"],
        "keyLocation": f"{base}/{site['indexnow_key']}.txt",
        "urlList": changed[:10000],
    }).encode()
    for ep in ENDPOINTS:
        req = urllib.request.Request(ep, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f"{ep} → {r.status}")
        except Exception as e:  # 알림 실패가 배포를 막지는 않아요
            print(f"{ep} → 실패: {e}")


if __name__ == "__main__":
    main()
