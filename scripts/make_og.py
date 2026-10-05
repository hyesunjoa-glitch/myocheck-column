#!/usr/bin/env python3
"""
카톡·인스타·X 공유 미리보기 이미지(1200×630)를 만들어요.

  python3 scripts/make_og.py          → 글마다 static/og/<주소>.jpg + 기본 이미지 static/og/default.jpg
  python3 scripts/make_og.py 주소     → 그 글 하나만 다시 만들기

새 글을 쓰거나 제목을 바꾸면 한 번 돌려 주세요. 이미지가 없는 글은 기본 이미지로 공유돼요.
필요한 것: pip install playwright pyyaml  (+ 브라우저)
"""
from __future__ import annotations

import asyncio
import base64
import html
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "og"
W, H = 1200, 630


def load_yaml(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def data_uri(p: Path) -> str:
    mime = "image/png" if p.suffix == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: %dpx; height: %dpx; }
body {
  font-family: "Noto Sans CJK KR", "Noto Sans KR", "Apple SD Gothic Neo", sans-serif;
  background: #0A0A0A; color: #fff; overflow: hidden; position: relative;
  word-break: keep-all; overflow-wrap: break-word;
}
.glow { position: absolute; right: -120px; top: -140px; width: 760px; height: 760px; border-radius: 50%%;
  background: radial-gradient(closest-side, rgba(0,253,170,.20), rgba(0,253,170,0)); }
.grain { position: absolute; inset: 0; background:
  repeating-linear-gradient(0deg, rgba(255,255,255,.018) 0 1px, transparent 1px 3px); }
.left { position: absolute; left: 76px; top: 70px; bottom: 64px; width: 690px; display: flex; flex-direction: column; }
.chip { align-self: flex-start; background: #00FDAA; color: #0A0A0A; font-weight: 800; font-size: 26px;
  padding: 7px 20px 8px; border-radius: 999px; letter-spacing: -0.3px; }
.title { margin-top: 34px; font-weight: 800; letter-spacing: -1.6px; line-height: 1.24; color: #fff; text-wrap: balance; }
.sub { margin-top: 20px; font-size: 27px; line-height: 1.45; color: #B9B9B9; font-weight: 500; letter-spacing: -0.4px; text-wrap: balance; }
.foot { margin-top: auto; display: flex; align-items: center; gap: 16px; }
.foot img { height: 34px; }
.foot span { font-size: 25px; color: #E9E9E9; font-weight: 700; letter-spacing: -0.3px; }
.foot i { font-style: normal; color: #7C7C7C; font-weight: 500; }
.face { position: absolute; right: 84px; top: 112px; width: 300px; text-align: center; }
.face .ring { width: 300px; height: 300px; border-radius: 50%%; padding: 7px;
  background: conic-gradient(from 210deg, #00FDAA, #0A0A0A 55%%, #00FDAA); }
.face .ring img { width: 100%%; height: 100%%; border-radius: 50%%; object-fit: cover; display: block; border: 6px solid #0A0A0A; }
.face p { margin-top: 22px; font-size: 26px; font-weight: 700; color: #fff; letter-spacing: -0.3px; }
.face p b { color: #00FDAA; }
.duo { position: absolute; right: 56px; top: 150px; width: 400px; height: 320px; }
.duo .ring { position: absolute; width: 236px; height: 236px; }
.duo .a { left: 0; top: 0; } .duo .b { right: 0; bottom: 0; }
""" % (W, H)


def ga(name: str) -> str:
    """이름 뒤 조사: 받침 있으면 '이', 없으면 '가'"""
    c = name[-1]
    return "이" if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else "가"


def title_size(t: str) -> int:
    n = len(t)
    if n <= 16:
        return 72
    if n <= 26:
        return 62
    if n <= 36:
        return 54
    return 46


def column_html(col: dict, cat: dict, ch: dict | None, logo: str) -> str:
    t = col["title"]
    face = ""
    if ch:
        face = (f'<div class="face"><div class="ring"><img src="{data_uri(ROOT / ch["image"])}"></div>'
                f'<p><b>{html.escape(ch["name"])}</b>{ga(ch["name"])} 답해요</p></div>')
    sub = col.get("subtitle") or ""
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="glow"></div><div class="grain"></div>
<div class="left">
  <span class="chip">{html.escape(cat['name'])} 칼럼</span>
  <h1 class="title" style="font-size:{title_size(t)}px">{html.escape(t)}</h1>
  {f'<p class="sub">{html.escape(sub)}</p>' if sub and len(t) <= 36 else ''}
  <div class="foot"><img src="{logo}" alt=""><span>묘책 칼럼 <i>· myocheck(묘책사주)</i></span></div>
</div>
{face}
</body></html>"""


def default_html(site: dict, chars: dict, logo: str) -> str:
    faces = [c for c in chars.values() if c.get("image")][:2]
    duo = ""
    if len(faces) == 2:
        duo = ('<div class="duo">' +
               f'<div class="ring face-ring a" style="border-radius:50%;padding:6px;background:conic-gradient(from 210deg,#00FDAA,#0A0A0A 55%,#00FDAA)"><img src="{data_uri(ROOT / faces[0]["image"])}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:6px solid #0A0A0A;display:block"></div>' +
               f'<div class="ring face-ring b" style="border-radius:50%;padding:6px;background:conic-gradient(from 30deg,#00FDAA,#0A0A0A 55%,#00FDAA)"><img src="{data_uri(ROOT / faces[1]["image"])}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;border:6px solid #0A0A0A;display:block"></div>' +
               '</div>')
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="glow"></div><div class="grain"></div>
<div class="left">
  <span class="chip">재회 · 이별 · 궁합</span>
  <h1 class="title" style="font-size:62px">실제로 올라온 연애 고민,<br>사주로 답해요</h1>
  <p class="sub">연락이 올지, 왜 헤어졌는지,<br>둘이 잘 맞는지</p>
  <div class="foot"><img src="{logo}" alt=""><span>묘책 칼럼 <i>· myocheck(묘책사주)</i></span></div>
</div>
{duo}
</body></html>"""


def read_column(p: Path) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", p.read_text(encoding="utf-8"), re.S)
    meta = yaml.safe_load(m.group(1)) or {}
    meta.setdefault("slug", p.stem)
    return meta


async def main(only: str | None):
    from playwright.async_api import async_playwright
    site = load_yaml(ROOT / "site.yml")
    chars = load_yaml(ROOT / "characters.yml")
    cats = {c["key"]: c for c in site["categories"]}
    logo = data_uri(ROOT / "static" / "img" / "logo.png")
    jobs = []
    if not only:
        jobs.append(("default", default_html(site, chars, logo)))
    for p in sorted((ROOT / "content" / "columns").glob("*.md")):
        if p.name.startswith("_"):
            continue
        col = read_column(p)
        if only and col["slug"] != only:
            continue
        cat = cats.get(col.get("category"), {"name": "묘책"})
        jobs.append((col["slug"], column_html(col, cat, chars.get(col.get("character") or ""), logo)))
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for slug, doc in jobs:
            await pg.set_content(doc, wait_until="load")
            await pg.wait_for_timeout(150)
            await pg.screenshot(path=str(OUT / f"{slug}.jpg"), type="jpeg", quality=88,
                                clip={"x": 0, "y": 0, "width": W, "height": H})
            print("  ✓", f"static/og/{slug}.jpg")
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
