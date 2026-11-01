"""클로드 코드 데이터 분석 박사 키우기 — 세이브 파일과 퀘스트 검사.

/키우기 스킬이 부른다. 표준 라이브러리만 쓴다. 같은 폴더 상태면 늘 같은 결과를 낸다.

  python doctor.py                       내 캐릭터 카드
  python doctor.py 시작 <이름> <마스코트>  캐릭터 만들기 (마스코트: 부엉이 고양이 펭귄 여우 거북이 토끼)
  python doctor.py 마스코트               고를 수 있는 마스코트
  python doctor.py 확인 [W1-화] [--스스로 도전 ...]   퀘스트 검사 → 경험치
  python doctor.py 도감 [칸 이름]          도감 보기 · 칸 체크
  python doctor.py 이름 <새 이름>          캐릭터 이름 바꾸기
  python doctor.py 올리기                  세이브를 내 GitHub(edata9-doctor)에 올린다

세이브: <edata9-work>/edata9-doctor/character.json (+ 캐릭터.svg · README.md)
작업 폴더를 찾는 순서는 /체크 2절과 같다. 시험할 때는 환경 변수 EDATA9_WORK 로 바꾼다.
"""
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "규칙.json"), encoding="utf-8"))
QUESTS = os.path.join(HERE, "퀘스트")
SAVE_DIR_NAME = "edata9-doctor"
WEEKDAYS = ("화", "수", "목", "금")
IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp")

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def today():
    t = os.environ.get("EDATA9_TODAY")          # 시험용
    return dt.date.fromisoformat(t) if t else dt.date.today()


def stop(msg):
    print(msg)
    sys.exit(1)


# ── 작업 폴더 · 세이브 ──────────────────────────────────────────
def work_dir():
    env = os.environ.get("EDATA9_WORK")
    if env:
        return env if os.path.isdir(env) else stop(f"EDATA9_WORK 폴더가 없습니다: {env}")
    p = os.path.abspath(os.getcwd())
    while True:
        if os.path.basename(p).lower() == "edata9-work":
            return p
        up = os.path.dirname(p)
        if up == p:
            break
        p = up
    for c in (r"C:\edata9-work", os.path.expanduser("~/edata9-work")):
        if os.path.isdir(c):
            return c
    stop("작업 폴더(edata9-work)를 찾지 못했습니다. VS Code에서 C:\\edata9-work 아래 폴더를 열고 다시 불러 주세요.")


def save_path(work):
    return os.path.join(work, SAVE_DIR_NAME, "character.json")


def load(work, must=True):
    p = save_path(work)
    if not os.path.exists(p):
        if must:
            stop("아직 캐릭터가 없습니다. `/키우기 시작` 으로 먼저 만들어 주세요.")
        return None
    return json.load(open(p, encoding="utf-8"))


def store(work, ch):
    d = os.path.join(work, SAVE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    ch["summary"] = summary(ch)
    with open(save_path(work), "w", encoding="utf-8", newline="\n") as f:
        json.dump(ch, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(d, "캐릭터.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(svg(ch))
    with open(os.path.join(d, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(readme(ch))


# ── 계산 (board/app.js 의 같은 이름 함수와 똑같이 셈한다) ─────────
def week_of(sid):
    return int(re.match(r"W(\d+)-", sid).group(1))


def day_of(sid):
    return sid.split("-")[1]


def quest_xp(sid, rec):
    """회차 하나의 퀘스트 경험치. 평일은 기본이 있어야 도전 · 고수가 붙는다. 토요일은 가장 높은 단계 하나."""
    x = RULES["xp"]
    if day_of(sid) == "토":
        got = [t for t in ("최소", "기본", "도전") if rec.get(t) and (t != "도전" or rec.get("기본"))]
        return max([x["토"][t] for t in got] or [0])
    if not rec.get("기본"):
        return 0
    return sum(x["평일"][t] for t in ("기본", "도전", "고수") if rec.get(t))


def total_xp(ch):
    x = RULES["xp"]
    q = sum(quest_xp(s, r) for s, r in ch.get("quests", {}).items())
    return q + x["캡처"] * len(ch.get("captures", {})) + x["도감"] * len(ch.get("dex", {}))


def level_floor(lv):
    L = RULES["level"]
    return round(L["k"] * (lv - 1) ** L["exp"])


def level_of(xp):
    lv = 1
    while lv < RULES["level"]["max"] and level_floor(lv + 1) <= xp:
        lv += 1
    return lv


def done(rec, sid):
    """그 회차를 끝냈나 — 평일은 기본, 토요일은 어느 단계든."""
    if not rec:
        return False
    if day_of(sid) == "토":
        return any(rec.get(t) for t in ("최소", "기본", "도전"))
    return bool(rec.get("기본"))


def grade_of(ch):
    """로드맵 3-1. 두 주 창마다 평일 70% 이상 + 토요일 1회 이상이면 한 등급. 박사는 W9-금(내 플러그인 공개)도."""
    q = ch.get("quests", {})
    P = RULES["promotion"]
    passed = 0
    for g in RULES["grades"][1:]:
        w0, w1 = g["window"]
        weeks = range(w0, w1 + 1)
        wd = [s for s in RULES["sessions"] if week_of(s) in weeks and day_of(s) in WEEKDAYS]
        sat = [s for s in RULES["sessions"] if week_of(s) in weeks and day_of(s) == "토"]
        ok_wd = sum(done(q.get(s), s) for s in wd)
        ok_sat = sum(done(q.get(s), s) for s in sat)
        if ok_wd >= P["weekday_ratio"] * len(wd) and ok_sat >= P["saturday_min"]:
            if g.get("also") and not done(q.get(g["also"]), g["also"]):
                continue
            passed += 1
    names = [g["name"] for g in RULES["grades"]]
    return names[min(passed, len(names) - 1)]


def hatched(ch):
    return any(done(r, s) for s, r in ch.get("quests", {}).items())


def summary(ch):
    xp = total_xp(ch)
    return {"xp": xp, "level": level_of(xp), "grade": grade_of(ch),
            "dex": len(ch.get("dex", {})), "hatched": hatched(ch)}


# ── 그림 ─────────────────────────────────────────────────────
def mascot(mid):
    for m in RULES["mascots"]:
        if m["id"] == mid:
            return m
    return RULES["mascots"][0]


def svg(ch):
    m = mascot(ch.get("mascot"))
    a = RULES["art"]
    if hatched(ch):
        inner = a["body"] + a["mascot"][m["id"]] + a["grade"][grade_of(ch)]
    else:
        inner = a["egg"]
    inner = (a["base"] + inner).replace("{C}", m["color"]).replace("{B}", m["belly"])
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120' width='240' height='240'>"
            f"<title>{esc(ch.get('name', ''))}</title>{inner}</svg>\n")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar(xp):
    lv = level_of(xp)
    if lv >= RULES["level"]["max"]:
        return "█" * 20 + "  만렙"
    lo, hi = level_floor(lv), level_floor(lv + 1)
    n = int(20 * (xp - lo) / max(1, hi - lo))
    return "█" * n + "░" * (20 - n) + f"  {xp} / {hi} (다음 레벨까지 {hi - xp})"


def week_line(ch, week):
    q = ch.get("quests", {})
    out = []
    for d in ("화", "수", "목", "금", "토"):
        sid = f"W{week}-{d}"
        if sid in RULES["sessions"]:
            out.append(f"{d} {'✓' if done(q.get(sid), sid) else '·'}")
    return "  ".join(out)


def current_week():
    t = today()
    week = 1
    for sid, d in RULES["sessions"].items():
        if d and dt.date.fromisoformat(d) <= t:
            week = max(week, week_of(sid))
    return week


def card(ch, gained=None):
    s = summary(ch)
    m = mascot(ch.get("mascot"))
    wk = current_week()
    lines = ["```",
             f"{m['emoji']} {ch['name']}  ·  {s['grade'] if s['hatched'] else '알'}  ·  Lv {s['level']}",
             f"경험치 {bar(s['xp'])}",
             f"도감 {s['dex']} / 40   ·   {wk}주 퀘스트  {week_line(ch, wk)}",
             "```"]
    if gained:
        lines.append("방금 받은 것: " + " · ".join(gained))
    if not s["hatched"]:
        lines.append("아직 알입니다. 첫 퀘스트의 기본 단계를 끝내면 깨어납니다.")
    lines.append(f"캐릭터 그림: `{SAVE_DIR_NAME}/캐릭터.svg`")
    return "\n".join(lines)


def readme(ch):
    s = summary(ch)
    m = mascot(ch.get("mascot"))
    return (f"# {m['emoji']} {ch['name']}\n\n<img src=\"캐릭터.svg\" width=\"200\" alt=\"{esc(ch['name'])}\">\n\n"
            f"| 등급 | 레벨 | 경험치 | 도감 |\n|---|---|---|---|\n"
            f"| {s['grade'] if s['hatched'] else '알'} | {s['level']} | {s['xp']} | {s['dex']} / 40 |\n\n"
            f"EDATA 9기 «{RULES['game']}» 의 세이브 파일입니다. `character.json` 을 반 전체 보드가 읽습니다.\n")


# ── 퀘스트 검사 ───────────────────────────────────────────────
def P(work, rel):
    return os.path.join(work, *rel.split("/"))


def jget(obj, path):
    for k in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return None
    return obj


def read_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def norm_hash(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def remote_json(name):
    """플러그인에 없는 퀘스트 파일을 공개 저장소에서 읽는다 — 매주 플러그인을 새로 받지 않게.
    읽기만 하고 아무것도 보내지 않는다. 받지 못하면 None."""
    import urllib.parse
    import urllib.request
    base = (read_json(os.path.join(HERE, "..", "설정.json")) or {}).get("quest_url")
    if not base:
        return None
    try:
        with urllib.request.urlopen(base + urllib.parse.quote(name), timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def mockup_prints():
    return read_json(os.path.join(QUESTS, "목업지문.json")) or {"topics": {}, "ids": []}


def mock_hash(mock):
    h = mockup_prints().get("files", {}).get(mock)
    if h:
        return h
    return ((remote_json("목업지문.json") or {}).get("files") or {}).get(mock)


def new_topics(work, c):
    """목업에 없던 주제 가운데 문항 파일이 있고 조건을 채운 것의 수."""
    tj = read_json(P(work, "gam-test/topics.json")) or {}
    ids = [t.get("id") for t in tj.get("topics", []) if isinstance(t, dict)]
    base = set(mockup_prints()["ids"])
    n = 0
    for i in ids:
        if not i or i in base:
            continue
        t = read_json(P(work, f"gam-test/topics/{i}.json"))
        if not t:
            continue
        qs = t.get("questions") or []
        if len(qs) < c.get("min_questions", 1):
            continue
        if "basis" in c.get("need", []) and not all(str(q.get("basis") or "").strip() for q in qs):
            continue
        if "caveat" in c.get("need", []) and not str(t.get("caveat") or "").strip():
            continue
        n += 1
    return n


def changed_topic(work):
    prints = mockup_prints()["topics"]
    for name, h in prints.items():
        p = P(work, f"gam-test/topics/{name}")
        if os.path.exists(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() != h:
            return True
    return False


def check(work, c, sid):
    """검사 하나 → (통과?, 설명)."""
    t = c["type"]
    if t == "all":
        rs = [check(work, x, sid) for x in c["of"]]
        return all(r[0] for r in rs), " · ".join(r[1] for r in rs if not r[0]) or c.get("label", "")
    if t == "any":
        rs = [check(work, x, sid) for x in c["of"]]
        return any(r[0] for r in rs), c.get("label", "")
    label = c.get("label", "")
    if t == "exists":
        return bool(glob.glob(P(work, c["path"]))), label
    if t == "nonempty":
        p = P(work, c["path"])
        return os.path.isfile(p) and open(p, encoding="utf-8", errors="replace").read().strip() != "", label
    if t == "glob_min":
        return len(glob.glob(P(work, c["pattern"]))) >= c["min"], label
    if t == "contains":
        p = P(work, c["path"])
        return os.path.isfile(p) and c["text"] in open(p, encoding="utf-8", errors="replace").read(), label
    if t == "json_ne":
        v = jget(read_json(P(work, c["path"])), c["key"])
        return v is not None and str(v).strip() not in ("", str(c["value"])), label
    if t == "json_list":
        lst = jget(read_json(P(work, c["path"])), c["key"]) or []
        ok = [x for x in lst if isinstance(x, dict)
              and all(str(x.get(k) or "").strip() for k in c.get("nonempty", []))
              and all(v in str(x.get(k) or "") for k, v in c.get("contains", {}).items())]
        return len(ok) >= c.get("min", 1), label
    if t == "git_commits_min":
        out = git(P(work, c["repo"]), "log", "--oneline")
        return out is not None and len(out.strip().splitlines()) >= c["min"], label
    if t == "git_commits_since":
        d = RULES["sessions"].get(sid) or today().isoformat()
        out = git(P(work, c["repo"]), "log", "--oneline", f"--since={d} 00:00")
        return out is not None and len(out.strip().splitlines()) >= c.get("min", 1), label
    if t == "git_remote":
        out = git(P(work, c["repo"]), "remote", "-v")
        return out is not None and c["contains"] in out, label
    if t == "file_changed":
        # 목업에서 받은 그대로가 아니다 — 줄바꿈 차이는 같은 것으로 본다
        p = P(work, c["path"])
        h = mock_hash(c["mock"])
        if not os.path.isfile(p) or not h:
            return False, label
        return norm_hash(open(p, "rb").read()) != h, label
    if t == "json_values":
        lst = jget(read_json(P(work, c["path"])), c["key"]) or []
        got = [x.get(c["field"]) for x in lst if isinstance(x, dict)]
        return got == c["equals"], label
    if t == "absent":
        for pat in c["patterns"]:
            for p in glob.glob(P(work, pat), recursive=True):
                if os.path.isfile(p) and c["text"] in open(p, encoding="utf-8", errors="replace").read():
                    return False, label
        return True, label
    if t == "gam_new_topics":
        return new_topics(work, c) >= c.get("min", 1), label
    if t == "gam_changed_topic":
        return changed_topic(work), label
    raise SystemExit(f"퀘스트 파일 오류: 모르는 검사 «{t}»")


def capture_found(work, sid):
    """작업 폴더 «캡처» 에 회차 이름이 들어간 그림, 또는 그날 찍은 그림."""
    d = RULES["sessions"].get(sid)
    folders = [P(work, "캡처")]
    home = os.path.expanduser("~")
    folders += [os.path.join(home, "Pictures", "Screenshots"),
                os.path.join(home, "OneDrive", "Pictures", "Screenshots"),
                os.path.join(home, "OneDrive", "사진", "스크린샷")]
    for f in folders:
        for p in glob.glob(os.path.join(f, "*")):
            if not p.lower().endswith(IMG):
                continue
            if f == folders[0] and sid in os.path.basename(p):
                return True
            if d and dt.date.fromtimestamp(os.path.getmtime(p)).isoformat() == d:
                return True
    return False


def session_today():
    t = today().isoformat()
    for sid, d in RULES["sessions"].items():
        if d == t:
            return sid
    return None


def cmd_check(work, args):
    ch = load(work)
    selfs = []
    sid = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--스스로", "--self"):
            selfs += [x for x in args[i + 1:] if not x.startswith("--")]
            break
        if re.fullmatch(r"W\d+-[화수목금토]", a):
            sid = a
        i += 1
    sid = sid or session_today()
    if not sid:
        stop("어느 회차인지 알려 주세요. 예: `/키우기 확인 W1-화`")
    qf = os.path.join(QUESTS, f"{sid}.json")
    if os.path.exists(qf):
        quest = json.load(open(qf, encoding="utf-8"))
    else:
        quest = remote_json(f"{sid}.json")
        if quest is None:
            stop(f"{sid} 퀘스트를 가져오지 못했습니다. 인터넷 연결을 확인하고 다시 불러 주세요. "
                 "그래도 안 되면 아직 준비되지 않은 회차입니다 — 강사가 그 주가 오기 전에 올려 둡니다. 늦게 받아도 경험치는 같습니다.")
        if quest.get("session") != sid:
            stop(f"{sid} 퀘스트 파일이 이상합니다. 강사에게 알려 주세요.")
    rec = ch.setdefault("quests", {}).setdefault(sid, {})
    q_before = quest_xp(sid, dict(rec))
    before_lv, was_hatched = level_of(total_xp(ch)), hatched(ch)
    before_grade = grade_of(ch)
    stamp = today().isoformat()
    rows, pending_self = [], []
    tiers = list(quest["tiers"].keys())
    for tier in tiers:
        spec = quest["tiers"][tier]
        if rec.get(tier):
            rows.append((tier, "✓", "이미 받았습니다"))
            continue
        if "self" in spec:
            if tier in selfs:
                rec[tier] = stamp
                rec.setdefault("스스로", []).append(tier)
                rows.append((tier, "✓", "스스로 체크 — " + spec["self"]))
            else:
                pending_self.append((tier, spec["self"]))
                rows.append((tier, "·", "스스로 체크 — " + spec["self"]))
            continue
        res = [check(work, c, sid) for c in spec["checks"]]
        if all(r[0] for r in res):
            rec[tier] = stamp
            rows.append((tier, "✓", spec.get("label", "")))
        else:
            rows.append((tier, "·", "아직 — " + " · ".join(r[1] for r in res if not r[0])))
    gained = []
    if quest_xp(sid, rec) > q_before:
        gained.append(f"+{quest_xp(sid, rec) - q_before} 퀘스트")
    if not ch.setdefault("captures", {}).get(sid) and capture_found(work, sid):
        ch["captures"][sid] = stamp
        gained.append(f"+{RULES['xp']['캡처']} 캡처")
    if not rec:
        ch["quests"].pop(sid, None)
    after_xp = total_xp(ch)
    store(work, ch)
    print(f"**{sid} 퀘스트 — {quest.get('title', '')}**\n")
    print("| 단계 | | 무엇 |\n|---|---|---|")
    for tier, mark, what in rows:
        print(f"| {tier} | {mark} | {what} |")
    print()
    if not ch.get("captures", {}).get(sid):
        print(f"캡처 +{RULES['xp']['캡처']}: 오늘의 캡처(«{quest.get('capture', '')}»)를 `C:\\edata9-work\\캡처` 폴더에 `{sid}` 로 시작하는 이름으로 저장하면 받습니다.\n")
    if pending_self:
        print("스스로 체크할 단계: " + " · ".join(f"{t}({w})" for t, w in pending_self)
              + f" — 했다면 `/키우기 확인 {sid} --스스로 {' '.join(t for t, _ in pending_self)}`\n")
    if not was_hatched and hatched(ch):
        print("🥚 → 알이 깨어났습니다!\n")
    if level_of(after_xp) > before_lv:
        print(f"⬆ 레벨 업! Lv {before_lv} → Lv {level_of(after_xp)}\n")
    if grade_of(ch) != before_grade:
        print(f"🎓 승급! {before_grade} → {grade_of(ch)}\n")
    print(card(ch, gained))


# ── 그 밖의 명령 ──────────────────────────────────────────────
def find_mascot(s):
    s = s.strip()
    for m in RULES["mascots"]:
        if s in (m["id"], m["name"], m["emoji"]):
            return m
    return None


def cmd_start(work, args):
    old = load(work, must=False)
    if old:
        print(f"이미 캐릭터가 있습니다. 이름을 바꾸려면 `/키우기 이름 <새 이름>`.\n")
        print(card(old))
        return
    if len(args) < 2 or not find_mascot(args[-1]):
        stop("이름과 마스코트가 필요합니다. 예: `/키우기 시작 부엉박사 부엉이`\n\n" + mascot_list())
    name = " ".join(args[:-1]).strip()[:16]
    m = find_mascot(args[-1])
    ch = {"game": "edata9-doctor", "v": RULES["version"], "name": name, "mascot": m["id"],
          "created": today().isoformat(), "quests": {}, "captures": {}, "dex": {}}
    store(work, ch)
    print(f"{m['emoji']} **{name}** 의 알을 받았습니다. {m['name']} — {m['line']}.\n")
    print(card(ch))
    print("\n체크아웃 때 `/키우기 확인` 을 부르면 그날 퀘스트를 검사하고 경험치를 줍니다.")


def mascot_list():
    return "\n".join(f"- {m['emoji']} {m['name']} — {m['line']}" for m in RULES["mascots"])


def norm(s):
    return re.sub(r"[\s`·()（）/!]", "", s).lower()


def cmd_dex(work, args):
    ch = load(work)
    if args and args[0] in ("체크", "check"):
        args = args[1:]
    if not args:
        have = ch.get("dex", {})
        print("| 견습생 | 조수 | 연구원 | 장인 | 박사 |\n|---|---|---|---|---|")
        cols = list(RULES["dex"].values())
        for r in range(8):
            print("| " + " | ".join(("✓ " if c[r] in have else "") + c[r] for c in cols) + " |")
        print()
        for g, items in RULES["dex"].items():
            print(f"{g} {sum(i in have for i in items)} / 8", end="   ")
        print("\n\n등급은 두 주마다 `/체크` 와 토요일 실습으로 오르고, 도감은 해 본 만큼 찹니다.")
        return
    want = norm(" ".join(args))
    allitems = [i for v in RULES["dex"].values() for i in v]
    hits = [i for i in allitems if norm(i) == want] or [i for i in allitems if want in norm(i)]
    if len(hits) != 1:
        stop("어느 칸인지 하나로 정하지 못했습니다. " + ("후보: " + ", ".join(hits) if hits else "`/키우기 도감` 으로 칸 이름을 보세요."))
    item = hits[0]
    if item in ch.setdefault("dex", {}):
        print(f"«{item}» 칸은 이미 채웠습니다.\n")
    else:
        before = level_of(total_xp(ch))
        ch["dex"][item] = today().isoformat()
        store(work, ch)
        print(f"도감 «{item}» 칸을 채웠습니다. +{RULES['xp']['도감']}\n")
        if level_of(total_xp(ch)) > before:
            print(f"⬆ 레벨 업! Lv {before} → Lv {level_of(total_xp(ch))}\n")
    print(card(ch))


def cmd_rename(work, args):
    ch = load(work)
    if not args:
        stop("새 이름을 적어 주세요. 예: `/키우기 이름 부엉박사`")
    ch["name"] = " ".join(args).strip()[:16]
    store(work, ch)
    print(card(ch))


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def cmd_push(work, args):
    ch = load(work)
    store(work, ch)
    d = os.path.join(work, SAVE_DIR_NAME)
    if not os.path.isdir(os.path.join(d, ".git")):
        code, out = run(["git", "init", "-b", "main"], d)
        if code:
            stop("git 저장소를 만들지 못했습니다:\n" + out)
    run(["git", "add", "-A"], d)
    s = summary(ch)
    code, out = run(["git", "commit", "-m", f"박사 키우기 — {s['grade'] if s['hatched'] else '알'} Lv {s['level']} ({today().isoformat()})"], d)
    if code and "nothing to commit" not in out and "nothing added" not in out:
        stop("저장 지점을 남기지 못했습니다. 이름 · 이메일이 없다는 말이면 Claude에게 «GitHub 계정의 이름과 이메일로 설정해줘» 라고 한 뒤 다시 불러 주세요.\n\n" + out[-600:])
    code, remotes = run(["git", "remote"], d)
    if "origin" not in remotes.split():
        code, out = run(["gh", "repo", "create", SAVE_DIR_NAME, "--public", "--source=.", "--push",
                         "--description", "EDATA 9기 박사 키우기 세이브"], d)
        if code:
            stop("GitHub에 저장소를 만들지 못했습니다. GitHub CLI 로그인이 안 됐으면 쉬는 시간에 손을 들어 주세요.\n\n" + out[-600:])
    else:
        code, out = run(["git", "push", "-u", "origin", "main"], d)
        if code:
            stop("올리지 못했습니다:\n" + out[-600:])
    code, login = run(["gh", "api", "user", "--jq", ".login"], d)
    print("세이브를 올렸습니다. 몇 분 뒤 반 전체 보드에 반영됩니다.\n")
    if not code and login:
        print(f"처음 올렸다면 줌 채팅에 이 한 줄을 남겨 주세요 → `박사키우기 {login}`\n")
    print(card(ch))


def main(argv):
    work = work_dir()
    if not argv or argv[0] in ("카드", "card"):
        ch = load(work, must=False)
        if not ch:
            print("아직 캐릭터가 없습니다. 이름과 마스코트를 정해 `/키우기 시작 <이름> <마스코트>` 로 만듭니다.\n\n" + mascot_list())
            return
        print(card(ch))
        return
    c, rest = argv[0], argv[1:]
    table = {"시작": cmd_start, "start": cmd_start, "확인": cmd_check, "check": cmd_check,
             "도감": cmd_dex, "dex": cmd_dex, "이름": cmd_rename, "rename": cmd_rename,
             "올리기": cmd_push, "push": cmd_push}
    if c in ("마스코트", "mascots"):
        print(mascot_list())
        return
    if c not in table:
        stop(f"모르는 명령 «{c}». 쓸 수 있는 것: 시작 · 확인 · 도감 · 이름 · 올리기 · 마스코트")
    table[c](work, rest)


if __name__ == "__main__":
    main(sys.argv[1:])
