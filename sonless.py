"""
손 없는 날 달력 페이지 (2026-11-14 초안 — 사장님 승인 전까지 공개 안 됨)

  주소: /son-eopneun-nal/ (목록)  ·  /son-eopneun-nal/2027/3/ (달마다)
  켜는 곳: site.yml  sonless_calendar.enabled
    · false → 실제 빌드(_site)에 페이지·사이트맵·푸터 링크가 하나도 안 나와요.
    · --preview 빌드에서는 스위치와 상관없이 다 보여요(시안 확인용).

날짜 계산
  · 양력 → 음력: 한국천문연구원(KARI) 기준 음력표를 담은 korean_lunar_calendar 0.4.0 (MIT, vendor/ 안 휠을 그대로 읽음 —
    GitHub Actions의 `pip install markdown jinja2 pyyaml`만으로도 돌아가요).
  · 손 없는 날 = 음력 날짜 끝자리가 9·0인 날 (9·10·19·20·29·30일).
  · 일진(그날의 간지) = 날짜만으로 정해지는 60일 주기. 라이브러리 값과, 1949-10-01 = 갑자일 기준 계산이 같은지 빌드 때 확인해요.
  · 독립 검산(천문 계산으로 초하루를 따로 구해 맞춰 보기): scripts/verify_sonless.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
_WHEEL = ROOT / "vendor" / "korean_lunar_calendar-0.4.0-py3-none-any.whl"
if str(_WHEEL) not in sys.path:
    sys.path.insert(0, str(_WHEEL))
from korean_lunar_calendar import KoreanLunarCalendar  # noqa: E402

SLUG = "son-eopneun-nal"
WEEK = "월화수목금토일"                      # date.weekday() 순서
GAN_KO, GAN_HJ = "갑을병정무기경신임계", "甲乙丙丁戊己庚辛壬癸"
JI_KO, JI_HJ = "자축인묘진사오미신유술해", "子丑寅卯辰巳午未申酉戌亥"
GAPJA_ANCHOR = dt.date(1949, 10, 1)          # 갑자일 (일진 계산 기준점)
SON_DAYS = (9, 10, 19, 20, 29, 30)


def day_ganji(d: dt.date) -> tuple[str, str]:
    i = (d - GAPJA_ANCHOR).days % 60
    return GAN_KO[i % 10] + JI_KO[i % 12], GAN_HJ[i % 10] + JI_HJ[i % 12]


def day_info(d: dt.date) -> dict:
    c = KoreanLunarCalendar()
    if not c.setSolarDate(d.year, d.month, d.day):
        raise ValueError(f"음력 변환 실패: {d}")
    ko, hj = day_ganji(d)
    lib = c.getGapJaString().split()[-1].removesuffix("일")      # 라이브러리 일진 (예: 정사일 → 정사)
    if lib != ko:
        raise ValueError(f"일진 계산이 서로 달라요: {d} 라이브러리 {lib} / 직접 계산 {ko}")
    lm, ld, leap = c.lunarMonth, c.lunarDay, bool(c.isIntercalation)
    holiday = ""
    if (lm, ld) == (1, 1) and not leap:
        holiday = "설날"
    elif (lm, ld) == (8, 15) and not leap:
        holiday = "추석"
    return {"date": d, "wd": WEEK[d.weekday()], "weekend": d.weekday() >= 5,
            "ly": c.lunarYear, "lm": lm, "ld": ld, "leap": leap,
            "lunar_text": f"음력 {'윤' if leap else ''}{lm}월 {ld}일",
            "ganji": ko, "ganji_hj": hj, "son": ld in SON_DAYS, "holiday": holiday}


def month_info(y: int, m: int) -> dict:
    first = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    days = [day_info(first + dt.timedelta(n)) for n in range((nxt - first).days)]
    lead = (first.weekday() + 1) % 7                       # 일요일 시작 달력에서 1일 앞 빈칸 수
    cells = [None] * lead + days
    cells += [None] * (-len(cells) % 7)
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]
    return {"y": y, "m": m, "days": days, "weeks": weeks, "son": [d for d in days if d["son"]]}


def months_in_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out, (y, m) = [], start
    while (y, m) <= end:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def short_day(d: dict) -> str:
    return f"{d['date'].day}일({d['wd']})"


def join_days(days: list[dict]) -> str:
    return "·".join(short_day(d) for d in days)


def lunar_span(mi: dict) -> str:
    a, b = mi["days"][0], mi["days"][-1]
    fa = f"{'윤' if a['leap'] else ''}{a['lm']}월 {a['ld']}일"
    fb = f"{'윤' if b['leap'] else ''}{b['lm']}월 {b['ld']}일"
    return f"음력 {fa}부터 {fb}까지"


def seo_title(y, m) -> str:
    return f"{y}년 {m}월 손 없는 날 달력 (음력·일진)"


def description(mi: dict) -> str:
    y, m, son = mi["y"], mi["m"], mi["son"]
    nums = "·".join(f"{d['date'].day}일" for d in son)
    s = (f"{y}년 {m}월 손 없는 날은 {nums}, 모두 {len(son)}일이에요. "
         f"달력과 표에 음력·요일·일진을 함께 적고, 손 없는 날의 뜻과 이사·결혼 날짜에 참고하는 법을 정리했어요.")
    if len(s) > 120:
        s = f"{y}년 {m}월 손 없는 날은 {nums}, 모두 {len(son)}일이에요. 음력·요일·일진과 이사·결혼에 참고하는 법을 정리했어요."
    return s


def faq(mi: dict, wedding_url: str | None) -> list[dict]:
    wed = (" 결혼 날짜와 손 없는 날의 차이는 「2027년 결혼하기 좋은 날」 칼럼에 따로 정리해 두었어요." if wedding_url else "")
    return [
        {"q": "손 없는 날은 무슨 뜻이에요?",
         "a": "음력 날짜 끝자리가 9나 0인 날(9·10·19·20·29·30일)이에요. 민속에서는 「손」이 날마다 방향을 바꿔 다니며 "
              "사람 일을 방해한다고 여겼고, 이 날들에는 손이 하늘로 올라가 어느 쪽에도 없다고 봤어요. "
              "그래서 이사·혼례처럼 큰일의 날을 잡을 때 참고해 온 기준이에요."},
        {"q": "손 있는 날에 이사해도 괜찮아요?",
         "a": "손 없는 날은 오래 이어져 온 풍속이고, 꼭 그날 이사해야 한다는 규칙은 없어요. "
              "전해 오는 이야기에서도 손이 있다고 여긴 방향만 피하면 된다고 보기도 해요. "
              "일정·비용·가족 사정을 함께 보고 정하시고, 이사 업체에는 날짜마다 견적이 다른지 물어보고 비교해 보세요."},
        {"q": "결혼이나 개업 날짜도 같은 기준으로 봐요?",
         "a": "손 없는 날은 이사뿐 아니라 혼례·개업 같은 큰일에도 함께 참고해 온 기준이에요. "
              "다만 누구에게나 같은 날이라, 두 사람 생년월일을 놓고 따로 날을 고르는 「택일」과는 보는 것이 달라요." + wed},
    ]


def build_pages(*, env, common: dict, site: dict, products: dict, live: list, write, root_for, urls: list,
                preview: bool, org: dict, tracked_url) -> dict | None:
    """페이지를 만들어요. 스위치가 꺼져 있고 시안 빌드도 아니면 아무것도 안 만들고 None."""
    cfg = site.get("sonless_calendar") or {}
    enabled = bool(cfg.get("enabled"))
    if not (enabled or preview):
        return None
    base = site["base_url"]
    start = tuple(int(x) for x in str(cfg.get("start", "2026-1")).split("-"))
    end = tuple(int(x) for x in str(cfg.get("end", "2027-12")).split("-"))
    ms = months_in_range(start, end)
    updated = cfg.get("updated") or dt.date.today()
    if isinstance(updated, str):
        updated = dt.date.fromisoformat(updated)
    prod_key = cfg.get("product") or "newyear-2027"
    prod = products.get(prod_key) or {}
    tp = (common.get("textpages") or {}).get(prod_key)
    hub_url = f"{base}/{SLUG}/"
    wedding = next((c for c in live if c.get("slug") == "wedding-date-2027"), None)
    og = f"{base}/static/og/default.jpg"

    data = {ym: month_info(*ym) for ym in ms}
    base_ctx = {k: v for k, v in common.items() if k != "og_image"}
    counts = [len(d["son"]) for d in data.values()]
    css_ver = (ROOT / "static" / "sonless.css").stat().st_mtime_ns % 100000

    for ym in ms:
        y, m = ym
        mi = data[ym]
        rel = f"{SLUG}/{y}/{m}/index.html"
        canonical = f"{base}/{SLUG}/{y}/{m}/"
        root = root_for(rel)
        i = ms.index(ym)
        prev_ym = ms[i - 1] if i > 0 else None
        next_ym = ms[i + 1] if i + 1 < len(ms) else None
        same = [(yy, m) for (yy, mm) in ms if mm == m and yy != y]
        slug = f"{SLUG}-{y}-{m}"
        col = {"slug": slug, "cta_line": None}
        cta_url = {p: tracked_url(prod.get("url", ""), position=p, slug=slug, product_key=prod_key)
                   for p in ("cta_mid", "cta_sticky", "cta_toc")}
        faqs = faq(mi, wedding and f"{base}/{wedding['url_path']}")
        title = f"{y}년 {m}월 손 없는 날"
        desc = description(mi)
        graph = [org,
                 {"@type": "Article", "headline": title, "name": seo_title(y, m), "description": desc,
                  "datePublished": updated.isoformat(), "dateModified": updated.isoformat(), "inLanguage": "ko-KR",
                  "mainEntityOfPage": {"@id": canonical}, "url": canonical, "image": og,
                  "about": {"@type": "Thing", "name": "손 없는 날"},
                  "author": {"@type": "Organization", "name": f"{site['brand']} 편집팀", "url": base + "/about/"},
                  "publisher": {"@id": org["@id"]}},
                 {"@type": "BreadcrumbList", "itemListElement": [
                     {"@type": "ListItem", "position": 1, "name": site["name"], "item": base + "/"},
                     {"@type": "ListItem", "position": 2, "name": "손 없는 날 달력", "item": hub_url},
                     {"@type": "ListItem", "position": 3, "name": title, "item": canonical}]},
                 {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["q"],
                                                      "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs]}]
        jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1).replace("</", "<\\/")
        page = env.get_template("sonless.html").render(
            **base_ctx, root=root, canonical=canonical, mi=mi, title=title, faqs=faqs, jsonld=jsonld,
            prev_ym=prev_ym, next_ym=next_ym, same=same, product=prod, product_key=prod_key, col=col, cta_url=cta_url,
            textpage=tp, wedding=wedding, lunar_span=lunar_span(mi), join_days=join_days, updated=updated,
            weekend_son=[d for d in mi["son"] if d["weekend"]], css_ver=css_ver, og_image=og,
            page_title=f"{seo_title(y, m)} | {common['brand_full']}", og_title=title, page_desc=desc)
        write(rel, page)
        urls.append((canonical, updated, hashlib.sha1(page.encode()).hexdigest()[:12]))

    # 목록(허브) 페이지
    years = sorted({y for y, _ in ms})
    rel = f"{SLUG}/index.html"
    hub_desc = (f"{years[0]}~{years[-1]}년 달마다 손 없는 날을 음력·요일·일진과 함께 달력으로 정리했어요. "
                "손 없는 날의 뜻, 손 있는 날 이사해도 되는지, 결혼·개업에도 같은 기준인지 쉽게 설명해요.")
    graph = [org,
             {"@type": "CollectionPage", "@id": hub_url, "url": hub_url, "name": f"손 없는 날 달력 {years[0]}·{years[-1]}",
              "description": hub_desc, "inLanguage": "ko-KR", "dateModified": updated.isoformat(),
              "publisher": {"@id": org["@id"]},
              "hasPart": [{"@type": "WebPage", "name": f"{y}년 {m}월 손 없는 날", "url": f"{base}/{SLUG}/{y}/{m}/"} for y, m in ms]},
             {"@type": "BreadcrumbList", "itemListElement": [
                 {"@type": "ListItem", "position": 1, "name": site["name"], "item": base + "/"},
                 {"@type": "ListItem", "position": 2, "name": "손 없는 날 달력", "item": hub_url}]}]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1).replace("</", "<\\/")
    page = env.get_template("sonless_hub.html").render(
        **base_ctx, root=root_for(rel), count_min=min(counts), count_max=max(counts), canonical=hub_url, years=years, data=data, ms=ms, jsonld=jsonld, css_ver=css_ver,
        join_days=join_days, og_image=og, updated=updated,
        page_title=f"손 없는 날 달력 {years[0]}·{years[-1]} (음력·일진) | {common['brand_full']}",
        og_title=f"손 없는 날 달력 {years[0]}·{years[-1]}", page_desc=hub_desc)
    write(rel, page)
    urls.append((hub_url, updated, hashlib.sha1(page.encode()).hexdigest()[:12]))
    return {"pages": len(ms) + 1, "enabled": enabled, "hub": f"{SLUG}/"}
