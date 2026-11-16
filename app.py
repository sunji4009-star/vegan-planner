import csv
import io
import random
import re
from collections import Counter
from html import escape as html_escape

import requests
import streamlit as st

st.set_page_config(page_title="비건 식단 플래너", page_icon="🥬", layout="wide")

st.markdown("""<style>
.block-container { padding-top: 2.2rem; max-width: 1250px; }
h1 { font-weight: 800; }
h2, h3 { font-weight: 700; }
[data-testid='stMetric'] { background:#F1F8E9; border:1px solid #DCEDC8; border-radius:12px; padding:14px 16px; }
[data-testid='stMetricValue'] { font-size:1.7rem; font-weight:700; color:#2E7D32; }
[data-testid='stSidebar'] { background:#F7FAF3; }
.plan-table { width:100%; border-collapse:separate; border-spacing:0; font-size:15px; line-height:1.55; }
.plan-table th { background:#2E7D32; color:#ffffff; padding:10px 12px; text-align:left; }
.plan-table td { padding:10px 12px; border-bottom:1px solid #E5E7EB; vertical-align:top; }
.plan-table tr:nth-child(even) td { background:#FAFAF6; }
.plan-table td.day { font-weight:700; white-space:nowrap; color:#2E7D32; }
.plan-table td.kcal { font-weight:700; white-space:nowrap; text-align:right; }
.plan-table ul { margin:0; padding-left:1.1rem; }
.plan-table li { margin-bottom:3px; }
.plan-table li small { color:#6B7280; }
.role { display:inline-block; font-size:11px; padding:1px 7px; border-radius:8px; margin-right:5px; background:#E8F5E9; color:#2E7D32; }
</style>""", unsafe_allow_html=True)

# ------------------------------------------------------------
# 인증키 (.streamlit/secrets.toml 에서 읽기, 없으면 sample)
# ------------------------------------------------------------
try:
    API_KEY = st.secrets["API_KEY"]
except Exception:
    API_KEY = "sample"

BASE_URL = "http://openapi.foodsafetykorea.go.kr/api/{key}/COOKRCP01/json/{start}/{end}"
PAGE = 1000

# ------------------------------------------------------------
# 비건 유형별 제외 재료 (키워드 방식이라 완벽하지 않아요)
# ------------------------------------------------------------
MEAT = ["소고기", "쇠고기", "돼지", "닭", "오리", "양고기", "베이컨", "햄", "소시지", "소세지",
        "스팸", "삼겹", "차돌", "사골", "곱창", "육포", "다짐육", "고기", "젤라틴", "라드",
        "갈비",
        # 요리 이름에 고기 글자가 없는 것들
        "불고기", "족발", "순대", "보쌈", "수육", "제육", "육회", "육전", "편육", "너비아니",
        "함박", "미트볼", "미트소스", "치킨", "너겟", "곰탕", "설렁탕",
        # 부위
        "양지", "사태", "등심", "안심", "채끝", "목살", "앞다리", "뒷다리", "항정", "갈매기살",
        "우족", "도가니", "막창", "대창", "내장", "껍데기", "선지", "살코기", "정육",
        "동그랑땡"]

FISH = ["생선", "멸치", "참치", "연어", "고등어", "갈치", "조기", "명태", "동태", "북어",
        "황태", "오징어", "낙지", "문어", "새우", "꽃게", "게살", "게맛살", "대게", "조개",
        "바지락", "홍합", "굴", "전복", "어묵", "맛살", "젓갈", "액젓", "까나리", "다랑어",
        "가쓰오", "한치", "주꾸미", "쭈꾸미", "꽁치", "장어", "해물", "해산물", "피시소스",
        # 민물·패류
        "다슬기", "올갱이", "새뱅이", "우렁", "골뱅이", "소라", "재첩", "꼬막", "가리비",
        "모시조개", "키조개", "백합", "석화", "미꾸라지", "추어", "붕어", "잉어", "가물치",
        "메기", "쏘가리", "빙어", "은어", "민물",
        # 생선류
        "코다리", "노가리", "삼치", "가자미", "광어", "우럭", "도미", "농어", "방어", "병어",
        "청어", "정어리", "전어", "민어", "숭어", "준치", "볼락", "임연수", "대구", "아구",
        "아귀", "복어", "홍어", "쥐치", "쥐포", "뱅어", "실치", "황석어", "참조기", "학꽁치",
        # 갑각류·기타 수산물
        "건새우", "마른새우", "보리새우", "홍게", "크랩", "랍스터", "가재", "성게", "해삼",
        "멍게", "미더덕", "오만둥이", "해파리", "진미채", "오징어채",
        # 가공품·알·소스
        "어류", "어패류", "수산물", "어육", "어간장", "굴소스", "명란", "창란", "어란",
       "연어알", "날치알", "캐비어", "새우젓", "참치캔", "금태", "대하"]
EGG = ["달걀", "계란", "메추리알", "마요네즈", "지단", "노른자", "흰자"]
DAIRY = ["우유", "치즈", "버터", "요구르트", "요거트", "생크림", "휘핑크림", "사워크림", "연유", "분유"]
HONEY = ["꿀", "벌꿀", "로열젤리"]

# 이 단어가 들어 있으면 비건 재료로 보고 먼저 지운 뒤 검사
SAFE_PHRASES = ["땅콩버터", "아몬드버터", "견과버터", "비건치즈", "견과치즈", "콩고기", "대체고기",
                "대체육", "비건고기", "식물성고기", "비건마요네즈", "아몬드우유", "귀리우유",
                "오트우유", "식물성우유", "붕어빵", "버섯굴소스", "버섯 굴소스", "채식굴소스",
                "채식 굴소스", "비건굴소스", "비건 굴소스",
                "버섯갈비", "비건갈비", "콩갈비", "두부갈비", "버섯떡갈비", "두부떡갈비",
                "버섯불고기", "두부불고기", "콩불고기", "비건불고기", "채식불고기", "우엉불고기",
                "버섯제육", "두부제육", "콩제육", "비건제육",
                "버섯육회", "비건육회", "두부육회", "가지육회",
                "버섯수육", "두부수육", "버섯탕수육", "두부탕수육", "채소탕수육",
                "두부보쌈", "보쌈김치",
                "두부함박", "콩함박", "버섯함박", "비건함박", "채식함박",
                "비건미트볼", "두부미트볼", "채식미트볼", "비건미트소스", "렌틸미트소스",
                "비건치킨", "채식치킨", "비건너겟", "채식너겟",
                "두부동그랑땡", "채소동그랑땡", "야채동그랑땡", "버섯동그랑땡", "연근동그랑땡",
                "비건동그랑땡", "채식동그랑땡", "콩동그랑땡", "감자동그랑땡"]

VEGAN_TYPES = {
    "비건 (동물성 전부 제외)": [MEAT, FISH, EGG, DAIRY, HONEY],
    "락토 (유제품 허용)": [MEAT, FISH, EGG],
    "오보 (달걀 허용)": [MEAT, FISH, DAIRY],
    "락토오보 (유제품·달걀 허용)": [MEAT, FISH],
    "페스코 (생선·유제품·달걀 허용)": [MEAT],
}

ACTIVITY = {
    "거의 안 움직임 (×1.2)": 1.2,
    "가벼운 활동 (×1.375)": 1.375,
    "보통 활동 (×1.55)": 1.55,
    "활발한 활동 (×1.725)": 1.725,
}
GOALS = {"체중 유지": 0, "체중 감량 (-300kcal)": -300, "체중 증량 (+300kcal)": 300}

MEAL_SPLIT = {"아침": 0.30, "점심": 0.35, "저녁": 0.35}
MEAL_ICON = {"아침": "🌅", "점심": "☀️", "저녁": "🌙"}


# ------------------------------------------------------------
# 레시피 불러오기
# ------------------------------------------------------------
def to_num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return 0.0


def parse_recipe(row):
    steps = []
    for i in range(1, 21):
        s = (row.get(f"MANUAL{i:02d}") or "").strip()
        if s:
            steps.append(re.sub(r"\s*[a-zA-Z]$", "", s))
    return {
        "id": row.get("RCP_SEQ"),
        "name": (row.get("RCP_NM") or "").strip(),
        "cat": (row.get("RCP_PAT2") or "").strip(),
        "kcal": to_num(row.get("INFO_ENG")),
        "car": to_num(row.get("INFO_CAR")),
        "pro": to_num(row.get("INFO_PRO")),
        "fat": to_num(row.get("INFO_FAT")),
        "na": to_num(row.get("INFO_NA")),
        "parts": (row.get("RCP_PARTS_DTLS") or "").strip(),
        "steps": steps,
    }


def fetch_range(key, start, end):
    resp = requests.get(BASE_URL.format(key=key, start=start, end=end), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    body = data.get("COOKRCP01", data)
    result = body.get("RESULT", {})
    code = result.get("CODE", "")
    if code == "INFO-200":
        return []
    if code != "INFO-000":
        raise RuntimeError(f"API 오류 ({code}): {result.get('MSG', '')}")
    return body.get("row", [])


@st.cache_data(ttl=60 * 60 * 24, show_spinner="레시피를 불러오는 중...")
def load_recipes(key):
    rows = []
    if key == "sample":
        rows = fetch_range(key, 1, 5)
    else:
        start = 1
        while start < 10000:
            chunk = fetch_range(key, start, start + PAGE - 1)
            rows.extend(chunk)
            if len(chunk) < PAGE:
                break
            start += PAGE
    return [parse_recipe(r) for r in rows]


def is_allowed(text, groups):
    for p in SAFE_PHRASES:
        text = text.replace(p, "")
    return not any(kw in text for group in groups for kw in group)


def daily_kcal(sex, age, height, weight, activity, goal):
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if sex == "남성" else -161)
    kcal = bmr * ACTIVITY[activity] + GOALS[goal]
    return int(round(max(kcal, 1200) / 10) * 10)


# ------------------------------------------------------------
# 영양 분석 기준값 (한국인 영양소 섭취기준)
# 출처: 보건복지부·한국영양학회 「한국인 영양소 섭취기준」
# ------------------------------------------------------------
CARB_RANGE = (55, 65)   # 탄수화물 에너지적정비율(%)
PRO_RANGE = (7, 20)     # 단백질 에너지적정비율(%)
FAT_RANGE = (15, 30)    # 지방 에너지적정비율(%)
NA_LIMIT = 2300         # 나트륨 만성질환위험감소섭취량(mg)
KCAL_TOLERANCE = 0.10   # 목표 열량 ±10%를 '적정'으로 봄

GREEN, ORANGE, RED = "#4CAF50", "#F5A623", "#E5534B"


def sum_nutrients(dishes):
    return {k: sum(r[k] for r in dishes) for k in ("kcal", "car", "pro", "fat", "na")}


def day_nutrients(day):
    dishes = [r for ds in day["meals"].values() for r in ds]
    return sum_nutrients(dishes)


def avg_nutrients(items):
    return {k: sum(x[k] for x in items) / len(items) for k in items[0]}


def macro_ratio(n):
    c, p, f = n["car"] * 4, n["pro"] * 4, n["fat"] * 9
    total = c + p + f
    if total == 0:
        return 0.0, 0.0, 0.0
    return c / total * 100, p / total * 100, f / total * 100


def range_status(v, lo, hi):
    if v < lo:
        return "부족", ORANGE
    if v > hi:
        return "초과", RED
    return "적정", GREEN


def bar_html(label, pct, text, color):
    pct = max(0, min(pct, 100))
    return (
        "<div style='margin:8px 0'>"
        "<div style='display:flex;justify-content:space-between;font-size:14px'>"
        f"<span>{label}</span><span>{text}</span></div>"
        "<div style='background:#e9ecef;border-radius:6px;height:14px'>"
        f"<div style='width:{pct:.0f}%;background:{color};height:14px;border-radius:6px'></div>"
        "</div></div>"
    )


def nutrient_panel(n, target):
    """열량·탄단지 비율·나트륨을 막대 그래프로 표시"""
    html = ""
    lo, hi = target * (1 - KCAL_TOLERANCE), target * (1 + KCAL_TOLERANCE)
    st_k, col = range_status(n["kcal"], lo, hi)
    html += bar_html("🔥 열량", n["kcal"] / target * 100,
                     f"{round(n['kcal']):,} / {target:,} kcal ({n['kcal'] / target * 100:.0f}%) · {st_k}", col)

    cr, pr, fr = macro_ratio(n)
    for name, ratio, rg, gram in (
        ("🍚 탄수화물", cr, CARB_RANGE, n["car"]),
        ("🫘 단백질", pr, PRO_RANGE, n["pro"]),
        ("🥑 지방", fr, FAT_RANGE, n["fat"]),
    ):
        s, c = range_status(ratio, rg[0], rg[1])
        html += bar_html(name, ratio,
                         f"{gram:.0f}g · 열량의 {ratio:.0f}% (권장 {rg[0]}~{rg[1]}%) · {s}", c)

    s, c = ("적정", GREEN) if n["na"] <= NA_LIMIT else ("초과", RED)
    html += bar_html("🧂 나트륨", n["na"] / NA_LIMIT * 100,
                     f"{round(n['na']):,} / {NA_LIMIT:,} mg ({n['na'] / NA_LIMIT * 100:.0f}%) · {s}", c)
    return html


def kcal_chart_html(values, target):
    """일별 열량 막대 그래프 (점선 = 목표)"""
    top = max(max(values), target) * 1.15
    line = target / top * 100
    bars, labels = "", ""
    for i, v in enumerate(values, 1):
        ok = abs(v - target) <= target * KCAL_TOLERANCE
        color = GREEN if ok else ORANGE
        bars += (f"<div title='{i}일차 {round(v)}kcal' "
                 f"style='flex:1;height:{v / top * 100:.1f}%;background:{color};"
                 "border-radius:3px 3px 0 0'></div>")
        labels += f"<div style='flex:1;text-align:center;font-size:10px'>{i}</div>"
    return (
        "<div style='position:relative;height:170px;display:flex;align-items:flex-end;"
        "gap:2px;border-bottom:1px solid #999'>"
        + bars
        + f"<div style='position:absolute;left:0;right:0;bottom:{line:.1f}%;"
        f"border-top:2px dashed {RED}'></div></div>"
        + f"<div style='display:flex;gap:2px'>{labels}</div>"
        + f"<div style='font-size:12px;margin-top:6px'>🟩 목표 ±10% 이내 &nbsp; 🟧 벗어남 "
        f"&nbsp; 빨간 점선: 목표 {target:,} kcal</div>"
    )


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------
# 식단 생성 (조합 품질 규칙 포함)
# ------------------------------------------------------------
TRIES = 600               # 한 끼를 구성할 때 시도하는 조합 수
REPEAT_PENALTY = 150      # 이미 나온 요리를 또 고르면 붙는 감점(kcal 환산)
SODIUM_WEIGHT = 0.05      # 한 끼 나트륨이 몫을 넘으면 mg당 감점
SAME_ING_PENALTY = 250    # 한 끼에 같은 재료 요리가 겹칠 때
DAY_ING_PENALTY = 80      # 같은 날 다른 끼니와 재료가 겹칠 때
SAME_METHOD_PENALTY = 120 # 같은 조리법(볶음+볶음 등)이 겹칠 때
HEAVY_PENALTY = 400       # 튀김·전류가 한 끼에 2개 이상일 때
BREAKFAST_HEAVY = 300     # 아침에 튀김·전류가 나올 때

NOT_DISH_END = ("소스", "드레싱", "양념장", "잼", "쨈", "청", "차", "주스", "스무디",
                "라떼", "에이드", "시럽", "페이스트")
NOT_DISH_IN = ("쿠키", "케이크", "푸딩", "머핀", "마들렌", "빙수", "아이스크림",
               "젤리", "타르트", "브라우니", "음료")
SOUP_END = ("국", "찌개", "탕", "전골")
NOODLE_BREAD = ("국수", "면", "파스타", "스파게티", "우동", "라면", "샌드위치", "토스트",
                "빵", "피자", "버거", "또띠아", "타코", "핫도그", "랩")
NO_SOUP_MAIN = ("국밥", "탕반", "죽")
METHODS = ["국수", "덮밥", "탕수", "전골", "찌개", "탕", "국", "볶음", "조림", "무침", "나물",
           "찜", "구이", "튀김", "부침", "전", "샐러드", "김치", "장아찌", "죽", "밥", "쌈",
           "말이", "냉채", "겉절이", "스테이크", "카레"]
HEAVY_METHODS = {"튀김", "탕수", "전", "부침"}
KEY_INGS = ["두부", "감자", "고구마", "호박", "버섯", "표고", "느타리", "새송이", "가지",
            "콩나물", "숙주", "시금치", "브로콜리", "양배추", "배추", "당근", "오이", "미역",
            "다시마", "깻잎", "양파", "파프리카", "토마토", "연근", "우엉", "도라지", "고사리",
            "취나물", "두유", "옥수수", "청경채", "쑥", "냉이", "달래", "병아리콩", "렌틸",
            "검은콩", "잡채", "떡"]


def is_dish(name):
    return not (name.endswith(NOT_DISH_END) or any(w in name for w in NOT_DISH_IN))


def is_noodle_bread(name):
    return any(k in name for k in NOODLE_BREAD)


def recipe_meta(r):
    name = r["name"]
    return {
        "method": next((m for m in METHODS if m in name), None),
        "keys": {k for k in KEY_INGS if k in name},
    }


def make_roles(with_soup, n_side):
    return ["주식"] + (["국"] if with_soup else []) + ["반찬"] * n_side


def meal_score(combo, target, ratio, meal, usage, day_keys, meta):
    score = abs(sum(c["kcal"] for c in combo) - target)
    score += REPEAT_PENALTY * sum(usage.get(c["id"], 0) for c in combo)
    score += max(0, sum(c["na"] for c in combo) - NA_LIMIT * ratio) * SODIUM_WEIGHT

    key_count = Counter(k for c in combo for k in meta[c["id"]]["keys"])
    score += SAME_ING_PENALTY * sum(n - 1 for n in key_count.values() if n > 1)
    score += DAY_ING_PENALTY * sum(1 for k in key_count if k in day_keys)

    methods = [meta[c["id"]]["method"] for c in combo]
    method_count = Counter(m for m in methods if m)
    score += SAME_METHOD_PENALTY * sum(n - 1 for n in method_count.values() if n > 1)

    heavy = sum(1 for m in methods if m in HEAVY_METHODS)
    if heavy >= 2:
        score += HEAVY_PENALTY
    if meal == "아침" and heavy:
        score += BREAKFAST_HEAVY
    return score


def build_plan(recipes, roles_by_meal, allow_noodle, days, daily_target, seed):
    rng = random.Random(seed)
    meta = {r["id"]: recipe_meta(r) for r in recipes}

    usable = [r for r in recipes if r["cat"] != "후식" and is_dish(r["name"])] or recipes
    rice = [r for r in usable
            if (r["cat"] == "밥" or "밥" in r["name"] or "죽" in r["name"])
            and not is_noodle_bread(r["name"])]
    rice_ids = {r["id"] for r in rice}
    alt = [r for r in usable if r["cat"] == "일품" and r["id"] not in rice_ids]

    main_pool = rice + (alt if allow_noodle else [])
    if len(main_pool) < 8:          # 후보가 너무 적으면 일품 전체를 허용
        main_pool = rice + alt
    main_pool = main_pool or usable
    side = [r for r in usable if r["cat"] == "반찬" and not r["name"].endswith(SOUP_END)] or usable
    soup = [r for r in usable if r["cat"] == "국&찌개"] or side
    pool = {"주식": main_pool, "국": soup, "반찬": side}

    usage = {}
    plan = []
    for day in range(1, days + 1):
        day_ids, day_keys = set(), set()
        meals = {}
        for meal, ratio in MEAL_SPLIT.items():
            target = daily_target * ratio
            roles = roles_by_meal[meal]
            best, best_score = None, float("inf")
            for _ in range(TRIES):
                first = rng.choice(pool["주식"])
                if first["id"] in day_ids:
                    continue
                eff = list(roles)
                if is_noodle_bread(first["name"]) or any(w in first["name"] for w in NO_SOUP_MAIN):
                    eff = ["반찬" if x == "국" else x for x in eff]
                combo, ids = [first], day_ids | {first["id"]}
                ok = True
                for role in eff[1:]:
                    cand = rng.choice(pool[role])
                    if cand["id"] in ids:
                        ok = False
                        break
                    ids.add(cand["id"])
                    combo.append(cand)
                if not ok:
                    continue
                score = meal_score(combo, target, ratio, meal, usage, day_keys, meta)
                if score < best_score:
                    best, best_score = combo, score
            if best is None:        # 후보가 너무 적을 때
                best = [rng.choice(pool[role]) for role in roles]
            for c in best:
                usage[c["id"]] = usage.get(c["id"], 0) + 1
                day_ids.add(c["id"])
                day_keys |= meta[c["id"]]["keys"]
            meals[meal] = best
        plan.append({"day": day, "meals": meals})
    return plan


def esc(s):
    """st.markdown / st.write 에서 ~ 와 $ 가 깨지지 않게"""
    return s.replace("~", "\\~").replace("$", "\\$")


def hesc(s):
    """HTML 안에 넣을 문자열 이스케이프"""
    return html_escape(str(s)).replace("$", "&#36;")


def plan_table_html(days):
    head = ("<tr><th>일차</th><th>🌅 아침</th><th>☀️ 점심</th><th>🌙 저녁</th>"
            "<th style='text-align:right'>하루 열량</th></tr>")
    body = ""
    for d in days:
        cells, total = "", 0
        for dishes in d["meals"].values():
            total += sum(r["kcal"] for r in dishes)
            items = "".join(
                f"<li><span class='role'>{hesc(r['cat'])}</span>{hesc(r['name'])} "
                f"<small>{round(r['kcal'])}kcal</small></li>" for r in dishes)
            cells += f"<td><ul>{items}</ul></td>"
        body += (f"<tr><td class='day'>{d['day']}일차</td>{cells}"
                 f"<td class='kcal'>{round(total):,} kcal</td></tr>")
    return f"<table class='plan-table'>{head}{body}</table>"


# ------------------------------------------------------------
# 알레르기 필터 / 미량영양소 위험도 추정
# ------------------------------------------------------------
# (키워드 목록, 예외 단어) - 예외 단어는 검사 전에 지워요
ALLERGENS = {
    "대두 (콩·두부·두유·된장·간장)": (
        ["대두", "서리태", "메주콩", "풋콩", "두부", "유부", "두유", "된장", "간장", "고추장",
         "쌈장", "청국장", "낫또", "템페", "콩가루", "콩나물", "비지", "콩"],
        ["완두콩", "강낭콩", "병아리콩", "렌틸콩", "깍지콩", "땅콩", "커피콩"],
    ),
    "땅콩": (["땅콩", "피넛"], []),
    "견과류 (호두·아몬드·잣 등)": (
        ["호두", "아몬드", "캐슈", "피스타치오", "헤이즐넛", "잣", "피칸", "마카다미아", "견과"], []),
    "밀 (밀가루·국수·빵·간장)": (
        ["밀가루", "통밀", "밀전병", "밀떡", "글루텐", "빵", "국수", "소면", "칼국수", "수제비",
         "우동", "스파게티", "파스타", "라면", "만두피", "또띠아", "부침가루", "튀김가루",
         "중력분", "박력분", "강력분", "간장"],
        ["쌀국수", "메밀국수"],
    ),
    "메밀": (["메밀"], []),
    "참깨": (
        ["참깨", "통깨", "깨소금", "깨가루", "깨즙", "검은깨", "흑임자", "참기름", "깨"],
        ["들깨", "깨끗", "깨뜨", "깨물"],
    ),
    "복숭아": (["복숭아", "백도", "황도", "천도"], []),
    "토마토": (["토마토", "케첩", "케찹"], []),
}

SUPP_OPTIONS = ["비타민 B12", "철분", "아연", "칼슘", "비타민 D",
                "오메가-3 (조류 유래 DHA/EPA)", "요오드", "종합 비타민·미네랄"]
FORTIFIED_OPTIONS = ["강화 두유·식물성 우유", "영양효모", "비타민 강화 시리얼", "칼슘 강화 두부"]
SUN_OPTIONS = ["거의 안 쬐요", "주 1~2회", "주 3회 이상 (한 번에 20분 이상)"]
SUN_FACTOR = {SUN_OPTIONS[0]: 0.0, SUN_OPTIONS[1]: 0.5, SUN_OPTIONS[2]: 1.0}

# 위험도 기준: 점수 65 이상 = 낮음, 35 이상 = 보통, 미만 = 높음
# sources: 공급원 식품군(군마다 하나라도 있으면 1개로 셈), need: 하루에 필요한 식품군 수
# plan_w: 식단에서 얻을 수 있는 최대 점수, supp_w / fort_w / sun_w: 영양제·강화식품·햇빛 가산점
MICRO = [
    {
        "key": "b12", "name": "비타민 B12",
        "why": "신경과 혈액 생성에 꼭 필요해요. 식물성 식품에는 사실상 없어서 비건은 영양제나 강화식품이 필수예요.",
        "sources": [("달걀", "계란", "메추리알"), ("우유", "치즈", "요구르트", "요거트"),
                    ("연어", "참치", "고등어", "멸치", "조개", "굴", "새우", "생선"), ("영양효모",)],
        "need": 1, "plan_w": 70, "supp": ["비타민 B12"], "supp_w": 70, "multi": True,
        "fort": ["강화 두유·식물성 우유", "영양효모", "비타민 강화 시리얼"], "fort_w": 35, "sun_w": 0,
        "tip": "비건은 B12 영양제를 꾸준히 먹는 게 가장 확실해요. 강화식품은 매일 여러 번 먹어야 효과가 있어요. "
               "용량은 전문가와 상의하고, 정기적으로 혈액검사(B12)를 받아보세요.",
    },
    {
        "key": "iron", "name": "철분",
        "why": "산소 운반과 피로 예방에 필요해요. 식물성 철분은 흡수율이 낮아서 더 신경 써야 해요.",
        "sources": [("두부", "순두부", "유부"),
                    ("렌틸", "병아리콩", "검은콩", "서리태", "강낭콩", "완두콩", "콩"),
                    ("시금치", "쑥", "냉이", "근대", "부추", "깻잎", "청경채", "케일"),
                    ("미역", "김", "다시마", "톳", "파래", "매생이"),
                    ("참깨", "통깨", "깨소금", "들깨", "깨가루"),
                    ("현미", "귀리", "퀴노아", "보리", "잡곡", "통밀", "흑미"),
                    ("브로콜리", "비트", "버섯", "표고", "양송이"),
                    ("건포도", "대추", "건살구", "무화과")],
        "need": 3, "plan_w": 70, "supp": ["철분"], "supp_w": 25, "multi": True,
        "fort": [], "fort_w": 0, "sun_w": 0,
        "tip": "파프리카·브로콜리·귤 같은 비타민 C 식품과 함께 먹으면 흡수가 좋아져요. "
               "식사 전후 1시간은 커피·차를 피하세요. 철분제는 혈액검사(페리틴) 후 전문가와 상의해서 드세요. 과잉도 해로워요.",
    },
    {
        "key": "zinc", "name": "아연",
        "why": "면역력과 상처 회복, 미각에 관여해요. 곡류·콩류의 피트산 때문에 흡수가 낮은 편이에요.",
        "sources": [("두부", "순두부"), ("콩", "렌틸", "병아리콩", "검은콩", "서리태"),
                    ("참깨", "통깨", "깨소금", "깨가루", "호박씨", "해바라기씨"),
                    ("캐슈", "잣", "호두", "아몬드", "견과"),
                    ("현미", "귀리", "퀴노아", "잡곡", "통밀", "흑미", "보리"),
                    ("버섯", "표고", "양송이", "새송이", "느타리"),
                    ("달걀", "계란"), ("치즈", "요구르트", "요거트", "우유"),
                    ("굴", "새우", "조개", "바지락", "홍합", "생선")],
        "need": 2, "plan_w": 70, "supp": ["아연"], "supp_w": 25, "multi": True,
        "fort": [], "fort_w": 0, "sun_w": 0,
        "tip": "콩과 곡물은 충분히 불리거나 발아·발효(된장, 템페)시켜 조리하면 흡수가 좋아져요.",
    },
    {
        "key": "calcium", "name": "칼슘",
        "why": "뼈와 치아 건강에 필요해요. 시금치처럼 수산이 많은 채소는 칼슘 흡수가 낮아요.",
        "sources": [("두부", "순두부"),
                    ("케일", "브로콜리", "청경채", "깻잎", "시래기", "무청", "냉이", "쑥"),
                    ("톳", "미역", "다시마", "김", "파래"),
                    ("참깨", "통깨", "깨소금", "깨가루", "아몬드"),
                    ("우유", "치즈", "요구르트", "요거트"),
                    ("멸치", "뱅어포", "잔새우", "건새우"), ("두유",)],
        "need": 2, "plan_w": 65, "supp": ["칼슘"], "supp_w": 25, "multi": False,
        "fort": ["강화 두유·식물성 우유", "칼슘 강화 두부"], "fort_w": 20, "sun_w": 0,
        "tip": "케일·청경채·브로콜리·칼슘 응고 두부·참깨·강화 두유가 좋은 공급원이에요.",
    },
    {
        "key": "vitd", "name": "비타민 D",
        "why": "칼슘 흡수와 뼈·면역에 관여해요. 음식만으로는 채우기 어려워서 햇빛이나 영양제가 중요해요.",
        "sources": [("버섯", "표고", "느타리", "양송이", "새송이", "팽이"), ("달걀", "계란"),
                    ("연어", "고등어", "참치", "꽁치", "갈치", "생선", "멸치"), ("우유", "치즈")],
        "need": 1, "plan_w": 15, "supp": ["비타민 D"], "supp_w": 60, "multi": True,
        "fort": ["강화 두유·식물성 우유", "비타민 강화 시리얼"], "fort_w": 15, "sun_w": 35,
        "tip": "겨울이나 실내 생활이 길면 햇빛만으로는 부족해요. 비건용 D 제품도 있으니 확인해보세요. "
               "혈액검사(25-OH 비타민 D)를 권장해요.",
    },
    {
        "key": "omega3", "name": "오메가-3",
        "why": "심혈관과 뇌 건강에 관여해요. 식물성(ALA)은 EPA·DHA로 바뀌는 비율이 낮아요.",
        "sources": [("들깨", "들기름"), ("호두",), ("아마씨", "치아씨", "대마씨", "햄프"),
                    ("연어", "고등어", "꽁치", "참치", "멸치", "정어리", "생선")],
        "need": 1, "plan_w": 45, "supp": ["오메가-3 (조류 유래 DHA/EPA)"], "supp_w": 55, "multi": False,
        "fort": [], "fort_w": 0, "sun_w": 0,
        "tip": "들기름·호두·아마씨·치아씨로 ALA를 채우고, 조류(algae) 유래 DHA/EPA 영양제도 고려해보세요.",
    },
    {
        "key": "iodine", "name": "요오드",
        "why": "갑상선 호르몬의 재료예요. 해조류를 안 먹는 비건은 부족하기 쉬워요.",
        "sources": [("김", "다시마", "미역", "톳", "파래", "매생이", "해조"),
                    ("우유", "치즈", "요구르트", "요거트"), ("달걀", "계란"),
                    ("생선", "멸치", "새우", "조개")],
        "need": 1, "plan_w": 80, "supp": ["요오드"], "supp_w": 30, "multi": True,
        "fort": [], "fort_w": 0, "sun_w": 0,
        "tip": "김·미역이 좋은 공급원이에요. 다시마는 요오드가 매우 많아서 매일 많이 먹으면 과잉이 될 수 있어요.",
    },
]


def has_allergen(text, selected, extra_words):
    for name in selected:
        kws, safe = ALLERGENS[name]
        t = text
        for s in safe:
            t = t.replace(s, "")
        if any(k in t for k in kws):
            return True
    return any(w in text for w in extra_words)


def micro_scores(plan, profile, weeks):
    # '김치'는 해조류 '김'으로 잘못 잡히지 않게 지우고 검사
    day_texts = [
        " ".join(r["name"] + " " + r["parts"] for ds in d["meals"].values() for r in ds).replace("김치", "")
        for d in plan
    ]
    results = []
    for m in MICRO:
        hits = [sum(1 for grp in m["sources"] if any(k in t for k in grp)) for t in day_texts]
        ok = [x >= m["need"] for x in hits]
        cov = sum(ok) / len(ok)
        points = cov * m["plan_w"]
        reasons = [f"식단에 공급원 식품이 충분히 나온 날 {sum(ok)}/{len(ok)}일 (+{cov * m['plan_w']:.0f}점)"]

        if any(s in profile["supps"] for s in m["supp"]):
            points += m["supp_w"]
            reasons.append(f"영양제 복용 (+{m['supp_w']}점)")
        elif m["multi"] and "종합 비타민·미네랄" in profile["supps"]:
            add = m["supp_w"] * 0.6
            points += add
            reasons.append(f"종합 비타민·미네랄 복용 (+{add:.0f}점, 함량이 제품마다 달라 60%만 반영)")

        fort = [f for f in profile["fortified"] if f in m["fort"]]
        if fort and m["fort_w"]:
            points += m["fort_w"]
            reasons.append(f"강화식품 섭취: {', '.join(fort)} (+{m['fort_w']}점)")

        if m["sun_w"]:
            add = m["sun_w"] * SUN_FACTOR[profile["sun"]]
            if add:
                points += add
                reasons.append(f"햇빛 노출 (+{add:.0f}점)")

        if m["key"] == "iron" and profile["coffee"]:
            points -= 15
            reasons.append("커피·차를 많이 마셔서 철분 흡수가 줄 수 있어요 (-15점)")
        if m["key"] == "iron" and profile["sex"] == "여성" and 19 <= profile["age"] <= 49:
            points -= 10
            reasons.append("월경이 있는 연령이라 철분 필요량이 높아요 (-10점)")
        if m["key"] in ("b12", "calcium", "vitd") and profile["age"] >= 50:
            points -= 10
            reasons.append("50세 이상은 흡수·합성이 줄어들어요 (-10점)")
        if profile["pregnant"]:
            points -= 15
            reasons.append("임신·수유 중에는 필요량이 늘어요 (-15점)")

        points = max(0, min(points, 100))
        if points >= 65:
            level, color, icon = "낮음", GREEN, "🟢"
        elif points >= 35:
            level, color, icon = "보통", ORANGE, "🟡"
        else:
            level, color, icon = "높음", RED, "🔴"

        week_txt = " · ".join(
            f"{w + 1}주차 {sum(ok[w * 7:(w + 1) * 7])}/{len(ok[w * 7:(w + 1) * 7])}일" for w in range(weeks)
        )
        results.append({**m, "points": points, "level": level, "color": color, "icon": icon,
                        "reasons": reasons, "week_txt": week_txt})
    return results


# ============================================================
# 화면
# ============================================================
st.title("🥬 비건 식단 플래너")

with st.sidebar:
    st.header("내 정보")
    sex = st.radio("성별", ["여성", "남성"], horizontal=True)
    age = st.number_input("나이", 10, 100, 30)
    height = st.number_input("키(cm)", 120.0, 220.0, 165.0)
    weight = st.number_input("몸무게(kg)", 30.0, 200.0, 60.0)
    activity = st.selectbox("활동량", list(ACTIVITY.keys()), index=1)
    goal = st.selectbox("목표", list(GOALS.keys()))

    st.header("식단 설정")
    vegan_type = st.selectbox("비건 유형", list(VEGAN_TYPES.keys()))
    weeks = st.radio("기간", [1, 2, 4], format_func=lambda w: f"{w}주", horizontal=True)
    with_soup = st.checkbox("국·찌개 포함", value=True)
    n_side = st.slider("반찬 가짓수 (한 끼)", 0, 5, 2)
    light_breakfast = st.checkbox("아침은 반찬 1개 줄이기")
    allow_noodle = st.checkbox("면·빵 요리도 주식으로 허용")
    st.caption(f"한 끼 = 주식 1 + 국 {1 if with_soup else 0} + 반찬 {n_side} "
               f"= 요리 {1 + (1 if with_soup else 0) + n_side}가지")

    st.header("알레르기·제외 재료")
    allergies = st.multiselect("알레르기 (해당 재료가 든 레시피 제외)", list(ALLERGENS.keys()))
    dislike_text = st.text_input("먹지 않는 재료 (쉼표로 구분)", placeholder="예: 가지, 고수")
    extra_words = [w.strip() for w in re.split(r"[,，\n]", dislike_text) if w.strip()]

    with st.expander("🩺 식습관·건강 설문 (미량영양소 분석용)"):
        supps = st.multiselect("복용 중인 영양제", SUPP_OPTIONS)
        fortified = st.multiselect("자주 먹는 강화식품", FORTIFIED_OPTIONS)
        sun = st.radio("햇빛 쬐는 정도", SUN_OPTIONS, index=1)
        coffee = st.checkbox("커피·녹차·홍차를 하루 3잔 이상 마셔요")
        pregnant = st.checkbox("임신 중이거나 수유 중이에요")

    st.header("요리 직접 제외")
    picked_block = []
    prev_plan = st.session_state.get("plan")
    if prev_plan:
        names = {r["id"]: r["name"] for d in prev_plan for ds in d["meals"].values() for r in ds}
        picked_block = st.multiselect("이상한 조합·싫은 요리 고르기", list(names.keys()),
                                      format_func=lambda i: names[i])
        st.caption("고른 요리는 '식단 만들기'를 다시 누르면 빠져요.")
    else:
        st.caption("식단을 만든 뒤에 여기서 요리를 골라 뺄 수 있어요.")
    n_blocked = len(st.session_state.get("blocked_all", set()))
    if n_blocked:
        st.caption(f"지금까지 제외한 요리: {n_blocked}개")
        if st.button("제외 목록 초기화"):
            st.session_state["blocked_all"] = set()
            st.rerun()

try:
    all_recipes = load_recipes(API_KEY)
except Exception as e:
    st.error(f"레시피를 불러오지 못했어요: {str(e).replace(API_KEY, '****')}")
    st.stop()

if API_KEY == "sample":
    st.warning("sample 키라 레시피가 5개뿐이에요. secrets.toml에 인증키를 넣어주세요.")

base_recipes = [
    r for r in all_recipes
    if r["kcal"] > 0 and is_allowed(r["name"] + " " + r["parts"], VEGAN_TYPES[vegan_type])
]
recipes = [
    r for r in base_recipes
    if not has_allergen(r["name"] + " " + r["parts"], allergies, extra_words)
]
if len(base_recipes) != len(recipes):
    st.caption(f"🚫 알레르기·제외 재료 때문에 레시피 {len(base_recipes) - len(recipes)}개를 뺐어요.")

if not recipes:
    st.error("조건에 맞는 레시피가 없어요. 비건 유형·알레르기를 바꾸거나 인증키를 확인해주세요.")
    st.stop()

target = daily_kcal(sex, age, height, weight, activity, goal)

c1, c2, c3 = st.columns(3)
c1.metric("하루 목표 열량", f"{target:,} kcal")
c2.metric("사용 가능한 레시피", f"{len(recipes)}개")
c3.metric("선택한 기간", f"{weeks}주 ({weeks * 7}일)")
st.caption(f"전체 {len(all_recipes)}개 중 '{vegan_type}' 기준으로 거른 결과예요. "
           "재료명 키워드로 거르는 방식이라 완벽하지 않으니 조리 전 재료를 꼭 확인하세요.")

if st.button("🍽️ 식단 만들기 / 다시 구성", type="primary"):
    blocked = set(st.session_state.get("blocked_all", set())) | set(picked_block)
    st.session_state["blocked_all"] = blocked
    pool_recipes = [r for r in recipes if r["id"] not in blocked]
    min_needed = 1 if API_KEY == "sample" else 15
    if len(pool_recipes) < min_needed:
        st.error("제외한 요리가 많아서 쓸 수 있는 레시피가 부족해요. 사이드바에서 제외 목록을 초기화해주세요.")
    else:
        roles_by_meal = {
            "아침": make_roles(with_soup, max(n_side - 1, 0) if light_breakfast else n_side),
            "점심": make_roles(with_soup, n_side),
            "저녁": make_roles(with_soup, n_side),
        }
        desc = f"주식 1 + 국 {1 if with_soup else 0} + 반찬 {n_side}"
        if light_breakfast:
            desc += ", 아침은 반찬 1개 적게"
        with st.spinner("식단을 구성하는 중..."):
            st.session_state["plan"] = build_plan(
                pool_recipes, roles_by_meal, allow_noodle, weeks * 7, target, random.randrange(10**9)
            )
        st.session_state["plan_info"] = {"weeks": weeks, "desc": desc, "target": target}

plan = st.session_state.get("plan")
if not plan:
    st.info("왼쪽에서 설정을 고른 뒤 '식단 만들기' 버튼을 눌러주세요.")
    st.stop()

info = st.session_state["plan_info"]
st.subheader(f"📅 {info['weeks']}주 식단표 ({info.get('desc', '')} × 3끼)")

# ---- 식단표 ----
rows, day_kcals, used_ids, total_dishes = [], [], set(), 0
for d in plan:
    row = {"주차": f"{(d['day'] - 1) // 7 + 1}주차", "일차": f"{d['day']}일차"}
    total = 0
    for meal, dishes in d["meals"].items():
        row[meal] = " · ".join(r["name"] for r in dishes)
        total += sum(r["kcal"] for r in dishes)
        used_ids.update(r["id"] for r in dishes)
        total_dishes += len(dishes)
    row["총 열량(kcal)"] = round(total)
    day_kcals.append(total)
    rows.append(row)

avg_kcal = round(sum(day_kcals) / len(day_kcals))
m1, m2, m3 = st.columns(3)
m1.metric("하루 평균 열량", f"{avg_kcal:,} kcal",
          delta=f"목표 대비 {avg_kcal - info['target']:+,} kcal")
m2.metric("서로 다른 요리", f"{len(used_ids)}개")
m3.metric("전체 요리 횟수", f"{total_dishes}회")

headers = list(rows[0].keys())

week_tabs = st.tabs([f"{w}주차" for w in range(1, info["weeks"] + 1)])
for wi, wt in enumerate(week_tabs):
    with wt:
        st.markdown(plan_table_html(plan[wi * 7:(wi + 1) * 7]), unsafe_allow_html=True)

buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=headers)
writer.writeheader()
writer.writerows(rows)
st.download_button(
    "📥 식단표 CSV로 저장",
    buf.getvalue().encode("utf-8-sig"),
    file_name="vegan_meal_plan.csv",
    mime="text/csv",
)

# ---- 영양 분석 ----
st.divider()
st.subheader("📊 영양 분석")

tgt = info["target"]
day_nuts = [day_nutrients(d) for d in plan]
tab_day, tab_week = st.tabs(["일일 분석", "주간 분석"])

with tab_day:
    sel = st.selectbox("날짜 선택", [d["day"] for d in plan],
                       format_func=lambda x: f"{x}일차", key="analysis_day")
    nut = day_nuts[sel - 1]
    st.markdown(nutrient_panel(nut, tgt), unsafe_allow_html=True)

    st.markdown("**끼니별 열량** (목표 배분: 아침 30% · 점심 35% · 저녁 35%)")
    meal_rows = []
    for meal, dishes in plan[sel - 1]["meals"].items():
        mn = sum_nutrients(dishes)
        meal_rows.append([meal, f"{round(mn['kcal'])} kcal", f"{round(tgt * MEAL_SPLIT[meal])} kcal",
                          f"{mn['car']:.0f}g", f"{mn['pro']:.0f}g", f"{mn['fat']:.0f}g",
                          f"{mn['na']:.0f}mg"])
    st.markdown(md_table(["끼니", "열량", "목표", "탄수화물", "단백질", "지방", "나트륨"], meal_rows))

with tab_week:
    st.markdown("**일별 열량 그래프**")
    st.markdown(kcal_chart_html([x["kcal"] for x in day_nuts], tgt), unsafe_allow_html=True)

    st.markdown("**주차별 평균 (하루 기준)**")
    week_rows = []
    for wk in range(1, info["weeks"] + 1):
        chunk = day_nuts[(wk - 1) * 7: wk * 7]
        a = avg_nutrients(chunk)
        cr, pr, fr = macro_ratio(a)
        ok_days = sum(1 for x in chunk if abs(x["kcal"] - tgt) <= tgt * KCAL_TOLERANCE)
        week_rows.append([f"{wk}주차", f"{round(a['kcal']):,} kcal",
                          f"{a['car']:.0f}g ({cr:.0f}%)", f"{a['pro']:.0f}g ({pr:.0f}%)",
                          f"{a['fat']:.0f}g ({fr:.0f}%)", f"{round(a['na']):,}mg",
                          f"{ok_days}/{len(chunk)}일"])
    st.markdown(md_table(["주차", "평균 열량", "탄수화물", "단백질", "지방", "나트륨", "열량 적정일"],
                         week_rows))

    st.markdown("**기간 평균 vs 권장 기준**")
    choice = st.selectbox("범위 선택", ["전체 기간"] + [f"{wk}주차" for wk in range(1, info["weeks"] + 1)],
                          key="analysis_week")
    if choice == "전체 기간":
        chunk = day_nuts
    else:
        wk = int(choice.replace("주차", ""))
        chunk = day_nuts[(wk - 1) * 7: wk * 7]
    st.markdown(nutrient_panel(avg_nutrients(chunk), tgt), unsafe_allow_html=True)

nut_buf = io.StringIO()
nut_writer = csv.writer(nut_buf)
nut_writer.writerow(["일차", "열량(kcal)", "탄수화물(g)", "단백질(g)", "지방(g)", "나트륨(mg)"])
for i, x in enumerate(day_nuts, 1):
    nut_writer.writerow([i, round(x["kcal"]), round(x["car"]), round(x["pro"]),
                         round(x["fat"]), round(x["na"])])
st.download_button("📥 일별 영양 분석 CSV로 저장", nut_buf.getvalue().encode("utf-8-sig"),
                   file_name="vegan_nutrition.csv", mime="text/csv")

# ---- 미량영양소 위험도 ----
st.divider()
st.subheader("🩺 미량영양소 위험도 추정")
st.caption("레시피 DB에는 비타민·미네랄 수치가 없어서, 식단에 들어간 공급원 식품이 얼마나 자주 나오는지와 "
           "설문 답변을 합쳐 대략 추정한 값이에요. 진단이 아닌 참고용이에요.")

if pregnant:
    st.error("임신·수유 중에는 비건 식단을 시작하거나 유지하기 전에 반드시 의사·영양사와 상담하세요.")

profile = {"supps": supps, "fortified": fortified, "sun": sun, "coffee": coffee,
           "pregnant": pregnant, "sex": sex, "age": age}
micro = micro_scores(plan, profile, info["weeks"])

risky = [m["name"] for m in micro if m["level"] == "높음"]
if risky:
    st.warning("⚠️ 결핍 위험이 높게 나온 영양소: " + ", ".join(risky))
else:
    st.success("✅ 위험이 '높음'으로 나온 영양소는 없어요. (그래도 정기 검진은 권장해요)")

micro_bars = ""
for m in micro:
    micro_bars += bar_html(f"{m['icon']} {m['name']}", m["points"],
                           f"보완 점수 {m['points']:.0f}/100 · 결핍 위험 {m['level']}", m["color"])
st.markdown(micro_bars, unsafe_allow_html=True)

for m in micro:
    with st.expander(f"{m['icon']} {m['name']} — 결핍 위험 {m['level']} ({m['points']:.0f}점)"):
        st.write(m["why"])
        st.markdown(f"**식단 공급원 출현** (하루 공급원 {m['need']}가지 이상 기준): {m['week_txt']}")
        st.markdown("**점수에 반영된 요인**")
        for rs in m["reasons"]:
            st.write(f"- {rs}")
        st.markdown(f"**보완 방법**  \n{m['tip']}")

st.caption("점수 기준: 65점 이상 🟢 낮음, 35점 이상 🟡 보통, 그 미만 🔴 높음. "
           "임신·성장기·만성질환이 있거나 증상이 있으면 혈액검사와 전문가 상담이 필요해요.")

# ---- 하루 상세 보기 ----
st.divider()
st.subheader("🔍 하루 상세 보기")
day_no = st.selectbox("날짜 선택", [d["day"] for d in plan],
                      format_func=lambda x: f"{x}일차", key="detail_day")
day = plan[day_no - 1]

cols = st.columns(3)
for col, (meal, dishes) in zip(cols, day["meals"].items()):
    with col:
        st.markdown(f"#### {MEAL_ICON[meal]} {meal}")
        st.caption(f"{round(sum(r['kcal'] for r in dishes))} kcal · 요리 {len(dishes)}가지")
        for r in dishes:
            with st.expander(f"{esc(r['name'])} · {round(r['kcal'])} kcal"):
                st.caption(f"{r['cat']} | 탄수화물 {r['car']:.0f}g · 단백질 {r['pro']:.0f}g · "
                           f"지방 {r['fat']:.0f}g · 나트륨 {r['na']:.0f}mg")
                st.markdown("**재료**")
                st.text(r["parts"] or "정보 없음")
                st.markdown("**만드는 법**")
                if r["steps"]:
                    for s in r["steps"]:
                        st.write(esc(s))
                else:
                    st.write("정보 없음")
