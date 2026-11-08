import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import {
  ASOF,
  DESIGN,
  FLOWS,
  HELP,
  MANUALS,
  NOTION_URL,
  STAFF,
  TEAMS,
  staffById,
  teamByKey,
  type HelpItem,
  type Staff,
  type TeamKey,
} from "@/lib/staff/data";

/** 직원 명부 — 옛 「묘책 직원 명부」(파란 게임 UI 한 장) 를 창고와 같은 캔바 구조(둘째 메뉴 + 흰 판)로 옮김.
 *  둘째 메뉴: 팀 6 + 도움 3 (이름만). 흰 판: 검색 → 팀 소개 → 일의 흐름 → 직원 목록(누르면 그 자리에서 펼쳐짐).
 *  자료는 전부 lib/staff/data.ts (옛 화면 글자 그대로). */
type Tab = TeamKey | HelpItem["k"];

const TEAM_COLOR: Record<TeamKey, string> = {
  reels: "#E8549C",
  ad: "#2F9BE8",
  page: "#3DBE4A",
  content: "#6F86E0",
  column: "#0FB58A",
  admin: "#3B4250",
};
const isTeam = (t: string): t is TeamKey => TEAMS.some((x) => x.k === t);
const isHelp = (t: string): t is HelpItem["k"] => HELP.some((x) => x.k === t);
const norm = (v: string) => v.normalize("NFC").toLowerCase().replace(/\s+/g, "");
const numOf = (id: string) => String(STAFF.findIndex((s) => s.id === id) + 1).padStart(2, "0");
const DESIGN_IDS = DESIGN.flatMap((d) => d[1].split("|"));

function readTab(): Tab {
  try {
    const h = window.location.hash.slice(1);
    const hs = h.startsWith("c-") ? staffById(h.slice(2)) : undefined;
    if (hs) return hs.t;
    const s = window.localStorage.getItem("staff_tab") ?? "";
    if (isTeam(s) || isHelp(s)) return s;
  } catch {
    /* 저장소를 못 읽어도 그냥 릴스팀부터 */
  }
  return "reels";
}
function readOpen(): string {
  try {
    const h = window.location.hash.slice(1);
    if (h.startsWith("c-") && staffById(h.slice(2))) return h.slice(2);
  } catch {
    /* 없음 */
  }
  return "";
}

const Chev = (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M6 9l6 6 6-6" />
  </svg>
);
const CopyIco = (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V5a1 1 0 0 1 1-1h10" />
  </svg>
);
function CopyBtn({ text, label = "복사", onCopy }: { text: string; label?: string; onCopy: (t: string) => void }) {
  return (
    <button type="button" className="cpy" onClick={() => onCopy(text)} title="복사">
      {CopyIco}
      {label}
    </button>
  );
}
const HelpIco: Record<HelpItem["icon"], ReactNode> = {
  book: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
      <path d="M4 19a2 2 0 0 1 2-2h13" />
    </svg>
  ),
  brush: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 4l-9 9M9 13l2 2M4 20c3 0 5-1 5-4a2 2 0 0 0-4 0c0 2-1 4-1 4z" />
    </svg>
  ),
  help: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01" />
    </svg>
  ),
};

export function StudioStaff({ onHome }: { onHome: () => void }) {
  const [tab, setTab] = useState<Tab>("reels");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState("");
  const [openMan, setOpenMan] = useState("");
  const [flash, setFlash] = useState("");
  const [toast, setToast] = useState("");
  const [booted, setBooted] = useState(false);

  // 처음 열 때: 주소(#c-직원id)나 지난번 탭을 읽는다. 창 밖 값이라 효과에서 읽는다.
  useEffect(() => {
    setTab(readTab());
    setOpen(readOpen());
    setBooted(true);
  }, []);
  useEffect(() => {
    if (!booted) return;
    try {
      window.localStorage.setItem("staff_tab", tab);
    } catch {
      /* 못 저장해도 됨 */
    }
  }, [tab, booted]);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(""), 1400);
    return () => window.clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (!flash) return;
    const el = document.getElementById("c-" + flash);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = window.setTimeout(() => setFlash(""), 1400);
    return () => window.clearTimeout(t);
  }, [flash]);

  function copy(text: string) {
    const done = () => setToast("복사됨");
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(done)
        .catch(() => setToast("복사가 안 됐어요 — 길게 눌러 복사해 주세요"));
    } else setToast("복사가 안 됐어요 — 길게 눌러 복사해 주세요");
  }
  function jump(id: string) {
    const s = staffById(id);
    if (!s) return;
    setQ("");
    setTab(s.t);
    setOpen(id);
    setFlash(id);
    try {
      window.history.replaceState(null, "", "#c-" + id);
    } catch {
      /* 없음 */
    }
  }
  function pickTab(t: Tab) {
    setQ("");
    setTab(t);
    setOpen("");
    window.scrollTo({ top: 0 });
  }

  const chip = (id: string) => {
    const s = staffById(id);
    return s ? (
      <button key={id} type="button" className="chip" onClick={() => jump(id)}>
        {s.name}
      </button>
    ) : null;
  };

  const detail = (s: Staff) => (
    <div className="detail">
      <p className="d">{s.d}</p>
      <div className="sec">
        <h5>능력 {s.ab.length}가지</h5>
        <ul className="abil">
          {s.ab.map(([a, say], i) => (
            <li key={i}>
              <span>
                {a}
                {say ? <q>{say}</q> : null}
              </span>
              {say ? <CopyBtn text={say} onCopy={copy} /> : null}
            </li>
          ))}
        </ul>
      </div>
      <div className="sec">
        <h5>제일 많이 쓰는 말</h5>
        <div className="saybox">
          <q>{s.say}</q>
          <CopyBtn text={s.say} onCopy={copy} />
        </div>
      </div>
      <dl className="meta">
        <dt>나오는 것</dt>
        <dd>{s.out}</dd>
        <dt>다음 직원</dt>
        <dd>{s.next.length ? <span className="chips">{s.next.map(chip)}</span> : "없음 — 여기서 끝나요"}</dd>
        {s.money ? (
          <>
            <dt>돈</dt>
            <dd>{s.money} — 시작 전에 예상 금액을 말하고 허락받아요</dd>
          </>
        ) : null}
        <dt>스킬 이름</dt>
        <dd>
          <code>{s.id}</code>
        </dd>
      </dl>
    </div>
  );

  const row = (s: Staff, showTeam = false) => {
    const t = teamByKey(s.t);
    const on = open === s.id;
    return (
      <article
        key={s.id}
        id={"c-" + s.id}
        className={"ev" + (on ? " open" : "") + (flash === s.id ? " flash" : "")}
        style={{ "--tc": TEAM_COLOR[s.t] } as CSSProperties}
      >
        <button
          type="button"
          className="row"
          aria-expanded={on}
          onClick={() => setOpen(on ? "" : s.id)}
        >
          <span className="no">{numOf(s.id)}</span>
          <span className="nm">
            <span className="h4">
              {s.name}
              {s.isNew ? <em className="new">신입</em> : null}
              {s.wait ? <em className="wait">⏳ 저장 대기</em> : null}
              {s.money ? <em className="money">돈 듦 · {s.money}</em> : null}
              {showTeam && t ? <em className="tk">{t.n}</em> : null}
            </span>
            <span className="one">{s.one}</span>
          </span>
          <span className="chev" aria-hidden="true">
            {Chev}
          </span>
        </button>
        {on ? detail(s) : null}
      </article>
    );
  };

  const needle = norm(q);
  let title = "";
  let body: ReactNode;
  if (needle) {
    const list = STAFF.filter((s) =>
      norm(
        [
          s.name,
          s.id,
          s.one,
          s.d,
          s.say,
          s.out,
          teamByKey(s.t)?.n ?? "",
          s.ab.map((a) => a.join(" ")).join(" "),
          DESIGN_IDS.includes(s.id) ? "디자인" : "",
        ].join(" "),
      ).includes(needle),
    );
    title = "찾은 직원";
    body = (
      <section aria-label="찾은 직원">
        <div className="list">
          {list.length ? (
            list.map((s) => row(s, true))
          ) : (
            <p className="empty">
              맞는 직원이 없어요. 「모르겠을 때」에서 스킬 직원에게 물어보세요.
            </p>
          )}
        </div>
      </section>
    );
  } else if (isTeam(tab)) {
    const t = teamByKey(tab);
    const list = STAFF.filter((s) => s.t === tab);
    const f = FLOWS[tab];
    title = t?.n ?? "";
    body = (
      <>
        <p className="intro">{t?.intro}</p>
        {f ? (
          <section className="flow" aria-label="일의 흐름">
            <h2>일의 흐름</h2>
            <div className="chain">
              {f.ids.map((x, i) => (
                <span key={i} className="step">
                  {i ? <span className="arr">→</span> : null}
                  {Array.isArray(x)
                    ? x.map((id, j) => (
                        <span key={id} className="alt">
                          {j ? <span className="arr">/</span> : null}
                          {chip(id)}
                        </span>
                      ))
                    : chip(x)}
                </span>
              ))}
            </div>
            <small>{f.note}</small>
          </section>
        ) : null}
        <section aria-label={title + " 직원"}>
          <div className="hd">
            <h2>직원</h2>
            <span className="hint">직원을 누르면 그 자리에서 능력이 펼쳐져요</span>
          </div>
          <div className="list">{list.map((s) => row(s))}</div>
        </section>
      </>
    );
  } else if (tab === "manual") {
    title = "사용 매뉴얼";
    body = (
      <>
        <p className="intro">도구 쓰는 법을 한 단계씩 쉬운 말로 적어 뒀어요. 이름을 누르면 그 자리에서 펼쳐져요.</p>
        <section aria-label="사용 매뉴얼">
          <div className="list">
            {MANUALS.map((m) => {
              const on = openMan === m.id;
              return (
                <article key={m.id} className={"ev" + (on ? " open" : "")} style={{ "--tc": "#E8549C" } as CSSProperties}>
                  <button type="button" className="row" aria-expanded={on} onClick={() => setOpenMan(on ? "" : m.id)}>
                    <span className="ic">{HelpIco.book}</span>
                    <span className="nm">
                      <span className="h4">
                        {m.name}
                        {m.tag ? <em className="wait">{m.tag}</em> : null}
                      </span>
                      <span className="one">{m.one}</span>
                    </span>
                    <span className="chev" aria-hidden="true">
                      {Chev}
                    </span>
                  </button>
                  {on ? (
                    <div className="detail">
                      {m.note ? <p className="d">{m.note}</p> : null}
                      {m.parts.map((p) => (
                        <div className="sec" key={p.h}>
                          <h5>{p.h}</h5>
                          <ol className="abil">
                            {p.steps.map(([a, say], i) => (
                              <li key={i}>
                                <span>
                                  <b>{i + 1}.</b> {a}
                                  {say ? <q>{say}</q> : null}
                                </span>
                                {say ? <CopyBtn text={say} onCopy={copy} /> : null}
                              </li>
                            ))}
                          </ol>
                        </div>
                      ))}
                      {m.notion ? (
                        <a className="ib" href={m.notion} target="_blank" rel="noopener noreferrer">
                          노션에서 크게 보기 ↗
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </section>
      </>
    );
  } else if (tab === "design") {
    title = "디자인은 누가?";
    body = (
      <>
        <p className="intro">
          디자인만 하는 직원은 따로 없어요. 무엇을 디자인하느냐에 따라 맡는 직원이 달라요 (10월 18일 결정). 이름을 누르면 그 직원의
          능력이 펼쳐져요.
        </p>
        <section aria-label="디자인 담당">
          <div className="dz">
            {DESIGN.map(([w, ids, n]) => (
              <div key={w} className="drow">
                <b>{w}</b>
                <span className="chips">{ids.split("|").map(chip)}</span>
                {n ? <small>{n}</small> : null}
              </div>
            ))}
          </div>
        </section>
      </>
    );
  } else {
    const ex = [
      "상세페이지 결제가 안 나오는데 누구한테 시켜?",
      "광고 영상 만들고 싶은데 뭐 써?",
      "지난주에 만든 거 어디 있는지 모르겠어",
    ];
    const ask = "스킬 직원, ○○ 하려면 뭐 써?";
    const sj = staffById("skill-jikwon");
    title = "모르겠을 때";
    body = (
      <>
        <p className="intro">
          어떤 직원을 불러야 할지 모르겠으면 스킬 직원에게 하고 싶은 일을 그냥 말하세요. 맞는 직원과 할 말을 알려줘요.
        </p>
        <section aria-label="이렇게 물어보세요">
          <h2>이렇게 물어보세요</h2>
          <div className="saybox big">
            <q>{ask}</q>
            <CopyBtn text={ask} onCopy={copy} />
          </div>
          <div className="ex">
            {ex.map((e) => (
              <div className="saybox" key={e}>
                <q>{e}</q>
                <CopyBtn text={e} onCopy={copy} />
              </div>
            ))}
          </div>
        </section>
        <section aria-label="물어볼 직원">
          <h2>물어볼 직원</h2>
          <div className="list">{sj ? row(sj) : null}</div>
        </section>
      </>
    );
  }

  return (
    <div className="store staff">
      <nav className="submenu" aria-label="직원 명부 메뉴">
        <button type="button" className="brand" onClick={onHome} title="홈으로">
          <i />
          직원 명부
        </button>
        <span className="grp">팀</span>
        {TEAMS.map((t) => (
          <button
            key={t.k}
            type="button"
            className={"sub" + (tab === t.k && !needle ? " on" : "")}
            aria-current={tab === t.k && !needle ? "page" : undefined}
            onClick={() => pickTab(t.k)}
          >
            <i style={{ background: TEAM_COLOR[t.k] }} />
            {t.n}
          </button>
        ))}
        <hr />
        <span className="grp">도움</span>
        {HELP.map((h) => (
          <button
            key={h.k}
            type="button"
            className={"sub" + (tab === h.k && !needle ? " on" : "")}
            aria-current={tab === h.k && !needle ? "page" : undefined}
            onClick={() => pickTab(h.k)}
          >
            {HelpIco[h.icon]}
            {h.n}
          </button>
        ))}
        <span className="sp" />
        <a className="sub link" href={NOTION_URL} target="_blank" rel="noopener noreferrer">
          노션 명부 열기 ↗
        </a>
      </nav>
      <div className="panelwrap">
        <div className="panel">
          <div className="head">
            <h1>{title}</h1>
            <label className="search">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-4-4" />
              </svg>
              <input
                type="search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="하고 싶은 일로 찾기 (예: 대본, 결제, 디자인)"
                aria-label="직원 찾기"
              />
              {q ? (
                <button type="button" className="clr" onClick={() => setQ("")}>
                  지우기
                </button>
              ) : null}
            </label>
          </div>
          {body}
          <p className="asof">{ASOF}</p>
        </div>
      </div>
      {toast ? (
        <div className="toast" role="status">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
