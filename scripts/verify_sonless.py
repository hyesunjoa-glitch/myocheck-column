#!/usr/bin/env python3
"""
손 없는 날 달력 독립 검산 (빌드에는 안 쓰여요 — 사람이 확인할 때만)

  pip install ephem
  python3 scripts/verify_sonless.py            # 2026-01 ~ 2027-12 전체
  python3 scripts/verify_sonless.py 2027-3     # 한 달만 자세히

방법 (sonless.py와 다른 길로 계산해서 맞춰 봐요)
  · 음력 날짜: 천문 계산 라이브러리(ephem)로 「삭(새 달)」 순간을 구하고, 한국 시간(UTC+9)으로 그날을 음력 1일로 봐요.
    그날부터 며칠째인지가 음력 날짜예요. (한국 음력은 한국 시간 기준 삭이 든 날을 초하루로 삼아요.)
  · 일진: 날짜 차이만으로 60일 주기를 세요. 기준점은 sonless.py(1949-10-01 갑자일)와 다른
    1900-01-01 = 갑술일(甲戌)을 써요.
  · 손 없는 날: 음력 날짜 끝자리 9·0.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import ephem

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sonless  # noqa: E402

KST = dt.timedelta(hours=9)
GAN, JI = "갑을병정무기경신임계", "자축인묘진사오미신유술해"
ANCHOR = dt.date(1900, 1, 1)
ANCHOR_IDX = 10   # 갑술 = 60갑자에서 11번째(0부터 10)


def new_moon_days(start: dt.date, end: dt.date) -> list[dt.date]:
    out, t = [], ephem.Date(dt.datetime.combine(start - dt.timedelta(40), dt.time()))
    while True:
        t = ephem.next_new_moon(t)
        kst = (ephem.Date(t).datetime() + KST).date()
        out.append(kst)
        if kst > end:
            return out
        t = ephem.Date(t + 1)


def lunar_day(d: dt.date, nms: list[dt.date]) -> int:
    last = max(n for n in nms if n <= d)
    return (d - last).days + 1


def ganji(d: dt.date) -> str:
    i = (ANCHOR_IDX + (d - ANCHOR).days) % 60
    return GAN[i % 10] + JI[i % 12]


def main():
    one = sys.argv[1] if len(sys.argv) > 1 else None
    ms = [tuple(map(int, one.split("-")))] if one else sonless.months_in_range((2026, 1), (2027, 12))
    nms = new_moon_days(dt.date(*ms[0], 1), dt.date(ms[-1][0], ms[-1][1], 28) + dt.timedelta(5))
    bad, total_days, total_son = 0, 0, 0
    for y, m in ms:
        mi = sonless.month_info(y, m)
        mine = [d["date"].day for d in mi["son"]]
        other = []
        for d in mi["days"]:
            total_days += 1
            ld = lunar_day(d["date"], nms)
            if ld != d["ld"] or ganji(d["date"]) != d["ganji"]:
                bad += 1
                print(f"  ✗ {d['date']} 음력 {d['ld']} vs 천문 {ld} / 일진 {d['ganji']} vs {ganji(d['date'])}")
            if ld % 10 in (9, 0):
                other.append(d["date"].day)
        total_son += len(mine)
        ok = "✅" if mine == other else "❌"
        print(f"{ok} {y}-{m:02d}  sonless.py {mine}  천문 계산 {other}")
        if one:
            for d in mi["days"]:
                print(f"     {d['date']} {d['wd']}  {d['lunar_text']:<12} {d['ganji']}일  {'← 손 없는 날' if d['son'] else ''}")
    print(f"\n{len(ms)}개월 · {total_days}일 비교 · 손 없는 날 {total_son}일 · 다른 날 {bad}일")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
