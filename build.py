#!/usr/bin/env python3
"""
묘책 칼럼 사이트 빌더

  python build.py            → 정식 빌드. '승인'된 글 중 안전검사를 통과한 글만 _site/ 에 만들어요.
  python build.py --preview  → 시안 빌드. 모든 글을 '시안' 표시와 함께 만들어요. 검색엔진 차단.
  python build.py --check    → 글마다 발행 가능한지, 안 되면 왜 안 되는지 알려줘요.
  python build.py --today 2026-10-25 → 그날 기준으로 예약 발행을 미리 돌려 봐요 (확인용)

필요한 것: pip install markdown jinja2 pyyaml
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
CONTENT = ROOT / "content" / "columns"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "_site"

# 이 표시가 글 어디에든 남아 있으면 발행하지 않아요.
#   [감수 자료 대기], [실제 고민 수집 대기], [상품 링크 대기] … 처럼 '대기'로 끝나는 자리 표시
PLACEHOLDER_RE = re.compile(r"\[[^\[\]\n]{0,30}대기\]")
MID_CTA_MARK = "[[상품버튼]]"
BUBBLE_RE = re.compile(r"\[\[(?P<who>[^\[\]|]+)\|(?P<formal>[^\[\]|]+)\|(?P<casual>[^\[\]|]+)\]\]")
TONES = ("formal", "casual")
SAJU_MARK = "[[사주해석]]"
SAJU_MAX_LINES = 4   # 「사주로 보면」은 항상 3~4줄 이내 (사장님 규칙)
CONCERN_MAX = 40     # 「이런 고민이 실제로 올라왔어요」 말풍선 한 개 — 360px 휴대폰에서 2줄 안쪽
SEO_TITLE_MAX = 30   # 검색 결과에 뜨는 제목은 30자 이내 (2026-10-05 확정)

# 쓰면 안 되는 말 — 발행을 막지는 않고 '확인해 보세요' 경고만 띄워요.
#   사연 인용이나 과거 일을 묘사한 문장도 걸리기 때문에, 사람이 보고 판단해요.
WARN_RE = re.compile(
    r"반드시|무조건|100%|확실히|틀림없이|절대로? ?(돌아|안 ?돼|성공)|액운|저주|흉살|큰일 ?(나|납)"
    r"|평생 ?(혼자|외롭|안 ?돼)|헤어질 운명|끝났어요|가망 ?없|찾아가(세요|보세요)|계속 연락|부계정|몰래"
)


# 「사주로 보면」에 쓰지 않는 사주 용어 (docs/review-guide.md 기준 2) — 경고만
JARGON_RE = re.compile(r"비견|겁재|식신|편재|정재|편관|정관|편인|정인|비겁|식상|재성|관성|인성|일간|일지|월지|대운|세운|월운|용신|신살|격국|공망|원진|천간")


def seo_title(col: dict) -> str:
    """검색 결과용 제목: seo_title이 있으면 그것, 없으면 원래 제목"""
    return str(col.get("seo_title") or col.get("title") or "").strip()


def saju_lines(col: dict) -> list:
    """frontmatter의 saju: (줄 목록 또는 한 덩어리 글) → 줄 목록. 비어 있으면 []"""
    v = col.get("saju")
    if not v:
        return []
    if isinstance(v, str):
        return [ln.strip() for ln in v.strip().splitlines() if ln.strip()]
    return [str(ln).strip() for ln in v if str(ln).strip()]
APPROVED = "승인"


# ─────────────────────────── 읽기 ───────────────────────────

def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_column(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: 맨 위 --- 머리말(frontmatter)이 없어요.")
    meta = yaml.safe_load(m.group(1)) or {}
    meta["body_md"] = m.group(2).strip()
    meta["file"] = path.name
    meta.setdefault("slug", path.stem)
    meta.setdefault("concerns", [])
    meta.setdefault("faq", [])
    for key in ("date", "updated"):
        v = meta.get(key)
        if isinstance(v, str) and v:
            meta[key] = dt.date.fromisoformat(v)
    meta["updated"] = meta.get("updated") or meta.get("date")
    return meta


# ─────────────────────────── 예약 발행 ───────────────────────────
KST = dt.timezone(dt.timedelta(hours=9))


def today_kst() -> dt.date:
    return dt.datetime.now(KST).date()


def as_date(v):
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)) if v else None


def schedule_columns(columns: list[dict], site: dict) -> dict | None:
    """예약 발행 날짜를 글마다 매겨요 (c["publish_on"]). launch_date가 비어 있으면 예약 발행을 쓰지 않아요(None).

    - publish_order 순서대로 하루(publish_every_days)에 한 칸씩. 칸은 승인 여부와 상관없이 고정이라,
      어떤 글이 제 날까지 승인되지 않으면 그날은 비고, 승인되는 날 바로 올라가요.
    - 순서에 없는 글은 목록 뒤에 이어 붙어요(작성일 → 주소 순).
    - 글 머리말의 publish_on 날짜가 있으면 그 날짜가 우선이에요.
    """
    launch = as_date(site.get("launch_date"))
    if not launch:
        return None
    every = int(site.get("publish_every_days") or 1)
    by_slug = {c["slug"]: c for c in columns}
    order = [by_slug[s] for s in (site.get("publish_order") or []) if s in by_slug]
    rest = sorted((c for c in columns if c not in order), key=lambda c: (c.get("date") or dt.date.max, c["slug"]))
    slot = 0
    for c in order + rest:
        fixed = as_date(c.get("publish_on"))
        if fixed:
            c["publish_on"] = fixed
        else:
            c["publish_on"] = launch + dt.timedelta(days=slot * every)
            slot += 1
    unknown = [s for s in (site.get("publish_order") or []) if s not in by_slug]
    return {"launch": launch, "every": every, "unknown": unknown}


# ─────────────────────────── 안전검사 ───────────────────────────

def all_strings(x) -> list[str]:
    """설정 안의 모든 글자를 꺼내요 (빈자리 검사용)."""
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for v in x.values() for t in all_strings(v)]
    if isinstance(x, list):
        return [t for v in x for t in all_strings(v)]
    return []


def publish_problems(col: dict, products: dict, categories: dict, characters: dict) -> list[str]:
    """발행하면 안 되는 이유 목록. 비어 있으면 발행 가능."""
    p: list[str] = []
    if col.get("status") != APPROVED:
        p.append(f"상태가 '{col.get('status', '없음')}' — '{APPROVED}'된 글만 발행해요")
    if col.get("category") not in categories:
        p.append(f"분류(category) '{col.get('category')}'가 site.yml에 없어요")
    prod = products.get(col.get("product") or "")
    if not prod:
        p.append("연결 상품(product)이 없어요 — 칼럼마다 상품을 하나 정해야 해요")
    elif not (prod.get("url") or "").strip():
        p.append(f"상품 '{prod.get('name')}' 링크가 비어 있어요 (products.yml)")
    if prod:
        for ph in sorted(set(PLACEHOLDER_RE.findall("\n".join(all_strings(prod))))):
            if ph != "[상품 링크 대기]":
                p.append(f"상품 '{prod.get('name')}'에 아직 채우지 않은 자리: {ph}")
    concerns = col.get("concerns") or []
    if not concerns:
        p.append("실제 고민(concerns)이 없어요 — 글감은 실제 댓글·DM·커뮤니티 글에서 가져와요")
    for i, c in enumerate(concerns, 1):
        if not (c or {}).get("source"):
            p.append(f"고민 {i}번에 출처(source)가 없어요")
    char_key = col.get("character")
    if char_key:
        ch = characters.get(char_key)
        if not ch:
            p.append(f"답하는 캐릭터 '{char_key}'가 characters.yml에 없어요")
        else:
            if ch.get("tone") not in TONES:
                p.append(f"캐릭터 '{ch.get('name')}' 말투(존댓말/반말)가 정해지지 않았어요 (characters.yml)")
    for field in ("title", "summary", "description", "date", "reviewer"):
        if not col.get(field):
            p.append(f"'{field}' 항목이 비어 있어요")
    texts = [col.get("body_md", ""), str(col.get("summary", "")), str(col.get("description", ""))]
    texts += [f"{f.get('q', '')} {f.get('a', '')}" for f in col.get("faq") or []]
    texts += [str((c or {}).get("text", "")) for c in concerns]
    texts += [str(a) for a in col.get("audience") or []]
    texts += all_strings(col.get("situations")) + all_strings(col.get("cover_say"))
    texts += [f"{s.get('label', '')} {s.get('text', '')}" for s in col.get("steps") or []]
    joined = "\n".join(texts)
    saju = saju_lines(col)
    if SAJU_MARK in joined and not saju:
        p.append("사주 해석 자리가 비어 있어요 [감수 자료 대기] — 해석 기준 문서가 오기 전엔 발행 안 해요")
    if saju and len(saju) > SAJU_MAX_LINES:
        p.append(f"「사주로 보면」이 {len(saju)}줄이에요 — {SAJU_MAX_LINES}줄 이내로 줄여야 해요")
    for ph in sorted(set(PLACEHOLDER_RE.findall(joined))):
        p.append(f"아직 채우지 않은 자리: {ph}")
    st = seo_title(col)
    if st and len(st) > SEO_TITLE_MAX:
        p.append(f"검색용 제목이 {len(st)}자예요 — {SEO_TITLE_MAX}자 이내로 seo_title을 적어 주세요")
    return p


def warn_words(col: dict) -> list[str]:
    """발행은 막지 않는 경고: 단정·겁주기·집착 조장 말이 들어 있는지"""
    texts = [col.get("body_md", ""), str(col.get("summary", ""))]
    texts += [f"{f.get('q', '')} {f.get('a', '')}" for f in col.get("faq") or []]
    texts += saju_lines(col) + all_strings(col.get("situations")) + all_strings(col.get("cover_say"))
    out = []
    for line in saju_lines(col):
        for m in JARGON_RE.finditer(line):
            out.append(f"사주 용어 '{m.group(0)}' — 「사주로 보면」에는 쉬운 말로 (docs/review-guide.md 기준 2)")
    for c in col.get("concerns") or []:   # 실제 고민은 휴대폰에서 2줄 이내 (2026-10-07) — 원문에서 후킹 부분만 잘라 '…'로
        t = str((c or {}).get("text", ""))
        if len(t) > CONCERN_MAX:
            out.append(f"실제 고민이 {len(t)}자예요 — 휴대폰에서 2줄을 넘을 수 있어요(약 {CONCERN_MAX}자 이내): {t[:20]}…")
    for line in "\n".join(texts).splitlines():
        for m in WARN_RE.finditer(line):
            s = max(0, m.start() - 15)
            out.append(f"'{m.group(0)}' — …{line[s:m.end() + 15].strip()}…")
    return out


# ─────────────────────────── 버튼 추적 ───────────────────────────

def tracked_url(url: str, *, position: str, slug: str, product_key: str) -> str:
    """상품 링크에 추적 태그(UTM)를 붙여요. 어느 글의 어느 버튼에서 왔는지 남아요."""
    if not url:
        return "#"
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query))
    q.update({
        "utm_source": "myocheck_column",
        "utm_medium": position,          # cta_mid / cta_toc / cta_sticky / rail
        "utm_campaign": slug,            # 어느 칼럼인지
        "utm_content": product_key,      # 어느 상품 버튼인지
    })
    return urlunparse(parts._replace(query=urlencode(q)))


# ─────────────────────────── 본문 변환 ───────────────────────────

def render_body(col: dict, env: Environment, ctx: dict) -> str:
    from markdown.extensions.toc import slugify_unicode
    md = markdown.Markdown(extensions=["extra", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False, "slugify": slugify_unicode}})
    body = col["body_md"]

    saju = saju_lines(col)
    if saju:
        saju_html = env.get_template("partials/saju.html").render(lines=saju, **ctx)
    else:
        saju_html = env.get_template("partials/saju_pending.html").render(**ctx)
    mid_html = env.get_template("partials/cta.html").render(position="cta_mid", **ctx)

    # 표시를 임시 토큰으로 바꿔 두었다가, 마크다운 변환 뒤에 블록으로 교체
    body = body.replace(SAJU_MARK, "\n\nMYOSAJUTOKEN\n\n")
    bubbles = []
    def _bub(m):
        bubbles.append(m.groupdict())
        return f"\n\nMYOBUBBLE{len(bubbles) - 1}TOKEN\n\n"
    body = BUBBLE_RE.sub(_bub, body)
    if MID_CTA_MARK in body:
        body = body.replace(MID_CTA_MARK, "\n\nMYOCTATOKEN\n\n", 1).replace(MID_CTA_MARK, "")
    else:
        # 표시가 없으면 소제목(##) 가운데쯤에 자동으로 넣어요
        heads = [m.start() for m in re.finditer(r"^## ", body, re.M)]
        if len(heads) >= 2:
            at = heads[len(heads) // 2]
            body = body[:at] + "\n\nMYOCTATOKEN\n\n" + body[at:]
        else:
            body = body + "\n\nMYOCTATOKEN\n"
    out = md.convert(body)
    col["toc"] = md.toc_tokens
    out = out.replace("<p>MYOSAJUTOKEN</p>", saju_html).replace("<p>MYOCTATOKEN</p>", mid_html)
    say = env.get_template("partials/say.html")
    for i, b in enumerate(bubbles):
        out = out.replace(f"<p>MYOBUBBLE{i}TOKEN</p>", say.render(**ctx, formal=b["formal"].strip(), casual=b["casual"].strip()))
    return out


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


# ─────────────────────────── 구조화 데이터 (AI·검색엔진용 설명표) ───────────────────────────

def org_node(site) -> dict:
    """운영사 정보 — 푸터에 보이는 값과 똑같이 (보이는 정보만 넣는다는 원칙)"""
    op = site.get("operator") or {}
    node = {
        "@type": "Organization",
        "@id": site["main_site"].rstrip("/") + "/#org",
        "name": site.get("brand_full") or site["brand"],
        "alternateName": [site["brand"], "묘책사주", "MYO:CHECK"],
        "url": site["main_site"],
        "logo": site["base_url"] + "/static/img/logo.png",
    }
    if op.get("legal_name"):
        node["legalName"] = op["legal_name"]
    if op.get("address"):
        node["address"] = {"@type": "PostalAddress", "streetAddress": op["address"], "addressCountry": "KR"}
    if op.get("phone"):
        node["telephone"] = op["phone"]
    return node


def jsonld_for_column(col, site, cat, canonical) -> str:
    org = org_node(site)
    page = {"@type": "WebPage", "@id": canonical, "url": canonical, "name": seo_title(col), "inLanguage": "ko-KR"}
    if col.get("reviewer"):
        page["reviewedBy"] = {"@type": "Person", "name": str(col["reviewer"])}
    if col.get("updated"):
        page["lastReviewed"] = col["updated"].isoformat()
    graph = [
        org,
        page,
        {
            "@type": "Article",
            "headline": col["title"],
            "description": col.get("description", ""),
            "abstract": plain(str(col.get("summary", ""))),
            "datePublished": col["date"].isoformat() if col.get("date") else None,
            "dateModified": col["updated"].isoformat() if col.get("updated") else None,
            "inLanguage": "ko-KR",
            "mainEntityOfPage": {"@id": canonical},
            "articleSection": cat["name"],
            "author": {"@type": "Organization", "name": f"{site['brand']} 편집팀", "url": site["base_url"] + "/about/"},
            "publisher": {"@id": org["@id"]},
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": site["name"], "item": site["base_url"] + "/"},
                {"@type": "ListItem", "position": 2, "name": cat["name"], "item": f"{site['base_url']}/{cat['key']}/"},
                {"@type": "ListItem", "position": 3, "name": seo_title(col), "item": canonical},
            ],
        },
    ]
    if col.get("faq"):
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": plain(markdown.markdown(f["a"]))}}
                for f in col["faq"]
            ],
        })
    data = {"@context": "https://schema.org", "@graph": graph}
    return json.dumps(data, ensure_ascii=False, indent=1, default=str).replace("</", "<\\/")


# ─────────────────────────── 빌드 ───────────────────────────

def build(preview: bool, today: dt.date | None = None) -> list[dict]:
    site = load_yaml(ROOT / "site.yml")
    today = today or today_kst()
    products = load_yaml(ROOT / "products.yml")
    characters = load_yaml(ROOT / "characters.yml") if (ROOT / "characters.yml").exists() else {}
    categories = {c["key"]: c for c in site["categories"]}
    base = site["base_url"].rstrip("/")
    site["base_url"] = base
    indexable = site.get("allow_indexing") and not preview

    columns = [read_column(p) for p in sorted(CONTENT.glob("*.md")) if not p.name.startswith("_")]
    for c in columns:
        c["problems"] = publish_problems(c, products, categories, characters)
        c["warnings"] = warn_words(c)
    sched = schedule_columns(columns, site)
    if sched is None and site.get("allow_indexing") and not preview:
        # 정식 오픈인데 예약 날짜가 없으면, 승인된 글이 한꺼번에 쏟아져요 → 빌드를 멈추고 지금 공개된 사이트를 그대로 둬요
        sys.exit("⛔ allow_indexing이 true인데 site.yml의 launch_date가 비어 있어요. "
                 "첫 글 발행일을 적어 주세요 (승인된 글이 한꺼번에 나가는 걸 막으려고 빌드를 멈췄어요).")
    for c in columns:
        c["waiting"] = bool(sched) and c["publish_on"] > today   # 승인됐지만 아직 차례가 안 온 글
        if sched and not c["waiting"]:
            # 화면·검색에 보이는 작성일 = 실제로 올라간 날
            c["date"] = max(c.get("date") or c["publish_on"], c["publish_on"])
            c["updated"] = max(c.get("updated") or c["date"], c["date"])
    live = columns if preview else [c for c in columns if not c["problems"] and not c["waiting"]]
    live.sort(key=lambda c: (c.get("date") or dt.date.min), reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(STATIC, OUT / "static")
    (OUT / ".nojekyll").write_text("")
    if (STATIC / "favicon.ico").exists():   # 검색 결과 옆 사이트 아이콘 — 검색엔진은 주소 맨 앞의 /favicon.ico를 먼저 찾아요
        shutil.copy(STATIC / "favicon.ico", OUT / "favicon.ico")

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "xml"]))
    env.filters["kdate"] = lambda d: f"{d.year}. {d.month}. {d.day}." if d else ""
    brand_full = site.get("brand_full") or site["name"]
    og_default = f"{base}/static/og/default.jpg"
    common = dict(site=site, categories=site["categories"], preview=preview, indexable=indexable, characters=characters,
                  year=dt.date.today().year, brand_full=brand_full, og_image=og_default,
                  org_jsonld=json.dumps({"@context": "https://schema.org", **org_node(site)}, ensure_ascii=False).replace("</", "<\\/"))

    def write(rel: str, text: str):
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def root_for(rel: str) -> str:
        depth = rel.count("/")
        return "../" * depth if depth else "./"

    urls = []  # (주소, 수정일, 지문)

    # 칼럼 페이지 — 서로 연결(함께 볼 글)되므로 주소·분류는 먼저 다 매겨 둔다
    for c in live:
        cat = categories.get(c.get("category"), {"key": "etc", "name": "기타", "intro": ""})
        c["cat"] = cat
        c["url_path"] = f"{cat['key']}/{c['slug']}/"
    for c in live:
        cat = c["cat"]
        prod_key = c.get("product") or ""
        prod = products.get(prod_key, {"name": "[상품 미정]", "button": "상품 보기", "hook": "", "url": ""})
        rel = f"{cat['key']}/{c['slug']}/index.html"
        canonical = f"{base}/{cat['key']}/{c['slug']}/"
        ctx = dict(common, root=root_for(rel), col=c, cat=cat, product=prod, product_key=prod_key,
                   character=characters.get(c.get("character") or ""),
                   tone=(characters.get(c.get("character") or "") or {}).get("tone") if (characters.get(c.get("character") or "") or {}).get("tone") in TONES else "formal",
                   others=[dict(v, key=k, track=tracked_url(v.get("url", ""), position="rail", slug=c["slug"], product_key=k))
                           for k, v in products.items() if k != prod_key and (v.get("url") or preview)],
                   read_min=max(1, round(len(plain(markdown.markdown(c["body_md"]))) / 500)),
                   cta_url={pos: tracked_url(prod.get("url", ""), position=pos, slug=c["slug"], product_key=prod_key)
                            for pos in ("cta_mid", "cta_sticky", "cta_toc")})
        # 카톡·SNS 공유 미리보기 이미지 — 글 전용(static/og/주소.jpg, scripts/make_og.py로 만듦)이 있으면 그것, 없으면 기본 이미지
        ctx["og_image"] = f"{base}/static/og/{c['slug']}.jpg" if (STATIC / "og" / f"{c['slug']}.jpg").exists() else og_default
        c["body_html"] = render_body(c, env, ctx)
        related = [o for o in live if o is not c and o.get("category") == c.get("category")][:6]
        page = env.get_template("column.html").render(
            **ctx, related=related, canonical=canonical,
            jsonld=jsonld_for_column(c, site, cat, canonical),
            page_title=f"{seo_title(c)} | {brand_full}", og_title=c["title"], page_desc=c.get("description", ""))
        write(rel, page)
        urls.append((canonical, c.get("updated"), hashlib.sha1(page.encode()).hexdigest()[:12]))

    # 분류 페이지
    for cat in site["categories"]:
        rel = f"{cat['key']}/index.html"
        items = [c for c in live if c.get("category") == cat["key"]]
        canonical = f"{base}/{cat['key']}/"
        write(rel, env.get_template("category.html").render(
            **common, root=root_for(rel), cat=cat, items=items, canonical=canonical,
            noindex_page=not items,   # 글이 0개인 분류는 검색에서 빼요 (빈 페이지는 사이트 점수를 깎아요)
            page_title=f"{cat['name']} 칼럼 | {brand_full}", page_desc=cat["intro"]))
        if items:
            urls.append((canonical, max((c["updated"] for c in items if c.get("updated")), default=None), ""))

    # 첫 화면 / 소개 / 404
    write("index.html", env.get_template("index.html").render(
        **common, root="./", items=live, canonical=base + "/",
        page_title=f"{site['name']} — {site['tagline']} | {brand_full}", page_desc=site["description"]))
    urls.insert(0, (base + "/", max((c["updated"] for c in live if c.get("updated")), default=None), ""))
    write("about/index.html", env.get_template("about.html").render(
        **common, root="../", canonical=base + "/about/",
        page_title=f"칼럼 원칙 | {brand_full}", page_desc="묘책 칼럼이 글을 만들고 검수하는 원칙 — 실제 고민, AI 사용 범위, 사람 검수, 운영사 정보"))
    urls.append((base + "/about/", None, ""))
    write("404.html", env.get_template("404.html").render(
        **common, root="/", canonical=None, noindex_page=True,
        page_title=f"페이지를 찾을 수 없어요 | {brand_full}", page_desc=""))

    # robots.txt / sitemap / llms.txt / 피드 / IndexNow 열쇠
    write("robots.txt", env.get_template("robots.txt").render(**common))
    write("sitemap.xml", env.get_template("sitemap.xml").render(urls=urls))
    write("llms.txt", env.get_template("llms.txt").render(**common, items=live, products=products))
    write("feed.xml", env.get_template("feed.xml").render(**common, items=live[:30]))
    write("CNAME", base.split("://", 1)[1])
    if site.get("indexnow_key"):
        write(f"{site['indexnow_key']}.txt", site["indexnow_key"])
    write("published.json", json.dumps(
        {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "urls": {u: h for u, _, h in urls if h}}, ensure_ascii=False, indent=1))
    build.sched, build.today = sched, today
    return columns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="시안 빌드 (모든 글, 검색 차단)")
    ap.add_argument("--check", action="store_true", help="글마다 발행 가능 여부만 확인")
    ap.add_argument("--today", help="예약 발행을 이 날짜 기준으로 돌려 보기 (예: 2026-10-25)")
    a = ap.parse_args()

    columns = build(preview=a.preview, today=as_date(a.today))
    ok = [c for c in columns if not c["problems"]]
    print(f"\n글 {len(columns)}개 중 발행 가능 {len(ok)}개" + (" (시안 빌드: 전부 '시안'으로 만듦)" if a.preview else ""))
    for c in columns:
        mark = "✅" if not c["problems"] else "⛔"
        print(f"  {mark} {c['file']} — {c.get('title', '')}")
        for prob in c["problems"]:
            print(f"       · {prob}")
        for w in c.get("warnings") or []:
            print(f"       ⚠️ 확인해 보세요: {w}")
    sched = build.sched
    if sched:
        print(f"\n📅 예약 발행 — 첫 글 {sched['launch']}, {sched['every']}일마다 1편 (오늘 {build.today}, 한국 시간)")
        for c in sorted(columns, key=lambda c: (c["publish_on"], c["slug"])):
            if c["problems"]:
                state = "차례 지남 · 승인되면 바로 올라가요" if c["publish_on"] <= build.today else "아직 발행 못 함 (위 ⛔ 참고)"
            else:
                state = "올라가 있음" if not c["waiting"] else "승인됨 · 대기"
            print(f"  {c['publish_on']}  {c['slug']}  ({state})")
        late = [c for c in columns if c["problems"] and c["publish_on"] <= build.today]
        if late:
            print(f"  ⚠️ 차례가 지났는데 아직 못 올라간 글이 {len(late)}편이에요. 한꺼번에 승인하면 같은 날 여러 편이 올라가요 —"
                  " 늦은 글은 머리말에 publish_on 날짜를 새로 적어 주세요.")
        for s_ in sched["unknown"]:
            print(f"  ⚠️ publish_order에 있는 '{s_}' 글 파일이 없어요")
    else:
        print("\n📅 예약 발행 꺼짐 (site.yml launch_date 비어 있음) — 승인된 글은 바로 올라가요. 시안 단계에서만 이렇게 둬요.")
    print(f"\n결과물: {OUT}")
    if a.check and len(ok) != len(columns):
        sys.exit(1)


if __name__ == "__main__":
    main()
