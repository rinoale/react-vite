"""Shared template generators for OCR training data.

Extracted from scripts/ocr/general_model/generate_training_data.py.
Both font-specific generators import from here to avoid duplication.
"""

import os
import re
import random

import yaml

# Dictionary paths (relative to project root)
DICT_PATHS = [
    "data/dictionary/reforge.txt",
    "data/dictionary/enchant_effect.txt",
    "data/dictionary/tooltip_general.txt",
]

# Source of truth paths
ENCHANT_YAML_PATH = "data/source_of_truth/enchant.yaml"
ITEM_NAME_DICT_PATH = "data/dictionary/item_name.txt"
REFORGE_DICT_PATH = "data/dictionary/reforge.txt"

# Section headers that need training boost (post-dedup).
# Formula: extra = ceil(target_images / VARIATIONS_PER_LABEL) - 1
HEADER_BOOSTS = [
    ('세공',         43),  # 44 total → ~132 images
    ('- 세공 -',      9),  # 10 total → ~30 images
    ('에르그',        26),  # 27 total → ~81 images
    ('- 에르그 -',    6),  # 7 total  → ~21 images
    ('인챈트',         9),  # 10 total → ~30 images
    ('- 인챈트 -',    3),  # 4 total  → ~12 images
    ('아이템 속성',   12),  # 13 total → ~39 images
    ('아이템 색상',   12),  # 13 total → ~39 images
    ('개조',           9),  # 10 total → ~30 images
    ('- 개조 -',      3),  # 4 total  → ~12 images
]

_NUM_RE = re.compile(r'\d+(?:\.\d+)?')
_RANGE_RE = re.compile(r'(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)')


def rand_int(lo, hi):
    return random.randint(lo, hi)


def rand_stat():
    return rand_int(0, 300)


def rand_pct():
    return f"{rand_int(1, 200)}%"


def rand_fraction():
    mx = rand_int(5, 100)
    cur = rand_int(0, mx)
    return f"{cur}/{mx}"

def rand_ranged():
    mx = rand_int(0, 500)
    cur = rand_int(0, mx)
    return f"{cur}/{mx}"

def rand_rgb():
    return rand_int(0, 255)


def rand_level():
    mx = rand_int(3, 25)
    cur = rand_int(1, mx)
    return f"{cur}/{mx}"


def rand_rank():
    return random.choice(['1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', 'S'])


def rand_float():
    return f"{rand_int(1, 99)}.{rand_int(0, 9)}%"


# ---------------------------------------------------------------------------
# Enchant effect loading from source of truth
# ---------------------------------------------------------------------------

def _load_enchant_effects():
    """Load all enchant effects from enchant.yaml.

    Returns list of (condition_or_None, effect_text) tuples.
    """
    if not os.path.exists(ENCHANT_YAML_PATH):
        print(f"Warning: {ENCHANT_YAML_PATH} not found, skipping enchant effects.")
        return []

    with open(ENCHANT_YAML_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    results = []
    for entry in data:
        for eff in entry.get('effects', []):
            if isinstance(eff, dict):
                cond = eff.get('condition')
                effect = eff.get('effect', '')
                results.append((cond, effect))
            else:
                results.append((None, eff))
    return results


def _randomize_numbers(text):
    """Replace each number in text with a random value in a similar range.

    Preserves format: integers stay integers, floats stay floats,
    ranges (N ~ N) keep lo <= hi.
    """
    # Handle ranges first (N ~ N)
    range_match = _RANGE_RE.search(text)
    if range_match:
        lo_str, hi_str = range_match.group(1), range_match.group(2)
        is_float = '.' in lo_str or '.' in hi_str
        if is_float:
            lo_val = float(lo_str)
            hi_val = float(hi_str)
            spread = hi_val - lo_val
            new_lo = round(random.uniform(max(0.1, lo_val * 0.5), hi_val * 1.5), 1)
            new_hi = round(new_lo + random.uniform(0, spread * 2), 1)
            lo_rep = f"{new_lo:.1f}" if '.' in lo_str else str(int(new_lo))
            hi_rep = f"{new_hi:.1f}" if '.' in hi_str else str(int(new_hi))
        else:
            lo_val = int(lo_str)
            hi_val = int(hi_str)
            spread = max(1, hi_val - lo_val)
            new_lo = rand_int(max(1, lo_val // 2), hi_val * 2)
            new_hi = new_lo + rand_int(0, spread * 2)
            lo_rep = str(new_lo)
            hi_rep = str(new_hi)
        text = text[:range_match.start()] + f"{lo_rep} ~ {hi_rep}" + text[range_match.end():]
        return text

    # Replace individual numbers
    def _replace_num(m):
        s = m.group(0)
        if '.' in s:
            val = float(s)
            new_val = round(random.uniform(max(0.1, val * 0.3), val * 3), 1)
            return f"{new_val:.1f}" if '.' in s else str(int(new_val))
        else:
            val = int(s)
            if val == 0:
                return str(rand_int(0, 10))
            return str(rand_int(max(1, val // 3), val * 3))

    return _NUM_RE.sub(_replace_num, text)


def _generate_enchant_lines(enchant_effects):
    """Generate training lines from enchant.yaml effects.

    For each effect:
    - Plain effects with numbers → randomize the numbers
    - Conditional effects → generate both full (condition + effect) and effect-only forms
    - Effects without numbers → include as-is
    """
    lines = []

    for condition, effect in enchant_effects:
        # Effect-only form (always included)
        if _NUM_RE.search(effect):
            for _ in range(2):
                lines.append(_randomize_numbers(effect))
        else:
            lines.append(effect)

        # Full condition+effect form
        if condition:
            full = f"{condition} {effect}"
            if _NUM_RE.search(full):
                for _ in range(2):
                    lines.append(_randomize_numbers(full))
            else:
                lines.append(full)

    return lines


# ---------------------------------------------------------------------------
# Set item name loading
# ---------------------------------------------------------------------------

def _load_set_item_names():
    """Extract set item skill names from item_name.txt.

    Pattern: '세트 효과 {skill_name} 강화 +N 주문서'
    """
    if not os.path.exists(ITEM_NAME_DICT_PATH):
        return []

    names = set()
    pat = re.compile(r'세트 효과 (.+?) 강화 \+\d+ 주문서')
    with open(ITEM_NAME_DICT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                names.add(m.group(1))
    return sorted(names)


# ---------------------------------------------------------------------------
# Reforge name loading
# ---------------------------------------------------------------------------

def _load_reforge_names():
    """Load all reforge option names from reforge.txt."""
    if not os.path.exists(REFORGE_DICT_PATH):
        return []

    with open(REFORGE_DICT_PATH, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


# ---------------------------------------------------------------------------
# General number format templates
# ---------------------------------------------------------------------------

def _generate_number_formats():
    """Generate standalone number format lines matching tooltip_general patterns.

    Covers: percentages, decimals, signed integers, level fractions, ranges.
    Extends range up to 1000.
    """
    lines = []

    # Percentages: N%, N.N%, N.NN%
    for _ in range(30):
        lines.append(f"{rand_int(1, 1000)}%")
    for _ in range(30):
        lines.append(f"{rand_int(0, 100)}.{rand_int(0, 9)}%")
    for _ in range(20):
        lines.append(f"{rand_int(0, 100)}.{rand_int(0, 99):02d}%")

    # Signed integers: +N, -N
    for _ in range(30):
        lines.append(f"+{rand_int(1, 1000)}")
    for _ in range(20):
        lines.append(f"-{rand_int(1, 1000)}")

    # Plain integers 0-1000
    for _ in range(30):
        lines.append(str(rand_int(0, 1000)))

    # Time format: N.NN 초
    for _ in range(20):
        lines.append(f"{rand_int(0, 30)}.{rand_int(0, 99):02d} 초")

    # Level fractions: (N/N 레벨)
    for _ in range(30):
        mx = rand_int(3, 25)
        cur = rand_int(1, mx)
        lines.append(f"({cur}/{mx} 레벨)")

    # Ranges: (N~N), (N.N%~N.N%)
    for _ in range(20):
        lo = rand_int(1, 500)
        hi = rand_int(lo, lo + 500)
        lines.append(f"({lo}~{hi})")
    for _ in range(20):
        lo_i = rand_int(1, 50)
        lo_d = rand_int(0, 9)
        hi_i = rand_int(lo_i, lo_i + 30)
        hi_d = rand_int(0, 9)
        lines.append(f"({lo_i}.{lo_d}%~{hi_i}.{hi_d}%)")

    return lines


# ---------------------------------------------------------------------------
# Main template generator
# ---------------------------------------------------------------------------

def generate_template_lines():
    """Generate training labels from tooltip line templates.

    No bullet/sub-bullet prefixes — the OCR model sees crops with
    prefixes already trimmed by the inference pipeline.
    """
    lines = []

    # --- Stat lines ---
    for _ in range(200):
        stat = random.choice(['방어력', '보호', '마법 방어력', '마법 보호', '최대대미지', '최소대미지'])
        lines.append(f"{stat} {rand_stat()}")

    for _ in range(200):
        lines.append(f"공격 {rand_ranged()}")

    for _ in range(50):
        lines.append(f"부상률 {rand_ranged()}%")

    for _ in range(50):
        stat = random.choice(['크리티컬', '밸런스'])
        lines.append(f"{stat} {rand_stat()}%")

    for _ in range(100):
        stat = random.choice(['탄환', '내구력'])
        lines.append(f"{stat} {rand_fraction()}")

    for _ in range(25):
        lines.append(f"숙련 {rand_stat()} {rand_float()}")

    # --- Color part sub-segments ---
    # Guarantee all A~F appear, then random for the rest
    for part in ['A', 'B', 'C', 'D', 'E', 'F']:
        lines.append(f"파트 {part}")
    for _ in range(94):
        part = random.choice(['A', 'B', 'C', 'D', 'E', 'F'])
        lines.append(f"파트 {part}")
    for _ in range(150):
        channel = random.choice(['R', 'G', 'B'])
        lines.append(f"{channel}:{rand_rgb()}")

    # --- Enchant effects from enchant.yaml ---
    enchant_effects = _load_enchant_effects()
    if enchant_effects:
        enchant_lines = _generate_enchant_lines(enchant_effects)
        lines.extend(enchant_lines)
        print(f"  Enchant effect lines from yaml: {len(enchant_lines)}")

    # --- Sub-bullet effects (no ㄴ prefix — OCR sees trimmed crops) ---
    sub_effects = ['보호', '방어력', '최대 내구도', '최대 공격력', '크리티컬',
                   '피어싱 레벨', '대미지 배율', '대미지', '쿨타임 감소',
                   '돌진 대미지', '돌진 사정 거리', '스매시 대미지',
                   '윈드밀 대미지', '파이널 히트 최종 대미지',
                   '파이널 스트라이크 분노 획득량', '윈드밀 최종 대미지',
                   '최소부상률', '지속대미지']
    for _ in range(100):
        effect = random.choice(sub_effects)
        val = rand_int(1, 100)
        sign = random.choice(['+', ''])
        unit = random.choice(['', '%', '% 증가'])
        lines.append(f"{effect} {sign}{val}{unit}")

    for _ in range(50):
        lines.append(f"대미지 배율 {rand_int(10, 150)}% 증가")
    for _ in range(50):
        lines.append(f"쿨타임 감소 {rand_int(1, 15)}.{rand_int(0, 99):02d}초 감소")
    for _ in range(50):
        effect = random.choice(['대미지', '최소부상률', '지속대미지'])
        lines.append(f"{effect} {rand_int(1, 200)} % 증가")

    # --- Item mods headers ---
    for _ in range(100):
        n = rand_int(1, 5)
        lines.append(f"일반 개조({n}/{n})")
    for _ in range(60):
        lines.append(f"일반 개조({rand_int(1,5)}/{rand_int(3,5)}), 보석 강화")
    for _ in range(60):
        stage = rand_int(1, 8)
        lines.append(f"특별 개조 R ({stage}단계)")
    for _ in range(60):
        stage = rand_int(1, 8)
        lines.append(f"특별 개조 S ({stage}단계)")

    # --- Item mods effects ---
    reforge_names = ['표면 강화', '경량화', '담금질', '보석 개조']
    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"{name}{n}")
    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"{name} {n}")

    # --- Special reforging ---
    for _ in range(20):
        lines.append(f"크리티컬 대미지 : {rand_int(100, 200)} +{rand_int(10, 80)}%")

    # --- Reforge lines (세공) — load all from dictionary ---
    reforge_all = _load_reforge_names()
    if reforge_all:
        for name in reforge_all:
            lines.append(f"{name}({rand_level()} 레벨)")
        # Extra random samples for variety
        for _ in range(100):
            name = random.choice(reforge_all)
            lines.append(f"{name}({rand_level()} 레벨)")
        print(f"  Reforge names from dictionary: {len(reforge_all)}")

    # --- Set item lines — load from item_name.txt ---
    set_item_names = _load_set_item_names()
    if set_item_names:
        for skill in set_item_names:
            lines.append(f"{skill} 강화 +{rand_int(1, 10)}")
        # Extra random samples
        for _ in range(50):
            skill = random.choice(set_item_names)
            lines.append(f"{skill} 강화 +{rand_int(1, 10)}")
        print(f"  Set item names from dictionary: {len(set_item_names)}")
    else:
        # Fallback if item_name.txt not available
        set_skills = ['돌진', '스매시', '윈드밀', '파이널 히트', '파이널 스트라이크']
        for _ in range(50):
            skill = random.choice(set_skills)
            lines.append(f"{skill} 강화 +{rand_int(1, 10)}")

    lines.extend([
        f"발동 조건: 강화 수치 {rand_int(5, 15)} 달성" for _ in range(20)
    ])

    # --- Piercing ---
    for _ in range(30):
        lvl = rand_int(1, 5)
        lines.append(f"피어싱 레벨 {lvl}")
    for _ in range(30):
        lvl = rand_int(1, 5)
        extra = random.choice(['', f'+ {rand_int(1,3)}'])
        lines.append(f"피어싱 레벨 {lvl}{extra}")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"마법 방어 {d}, 마법 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  마법 방어 {d}, 마법 보호 {p} 차감")

    piercing_note = ['(피어싱이 부여된 장비를 양 쪽에 착용 시, 높은 쪽 적용)',
                     '(피어싱이 부여된 장비를 양 쪽에 착용 시, 높은 쪽',
                     '(피어싱)이 부여된 장비를 양 쪽에 착용 시, 높은 쪽',
                     '적용)']
    lines.extend(piercing_note)

    # --- Hashtag lines ---
    tags = ['#남성 전용', '#여성 전용', '#인간, 자이언트 전용', '#대장장이 수리',
            '#의류점 수리', '#플레타 수리', '#반호르 주점 수리',
            '#인챈트 실패 시 아이템 보호', '#수리 실패시 아이템 보호',
            '#거래 불가', '#은행 불가', '#펫 보관 불가', '#염색 불가',
            '#소유권 보존', '#파트너 선물 및 착용 불가', '#계승 불가']
    for _ in range(50):
        n = rand_int(2, 5)
        selected = random.sample(tags, min(n, len(tags)))
        lines.append(' '.join(selected))

    # --- Price lines ---
    for _ in range(30):
        price = random.choice([f'{rand_int(100, 99999)} 골드', f'{rand_int(1, 99)}만 골드', '판매불가'])
        lines.append(f"상점판매가 : {price}")

    # --- Grade lines ---
    grades = ['마스터', '에픽', '엘리트', '레어', '일반']
    for _ in range(60):
        grade = random.choice(grades)
        lvl = rand_int(1, 1000)
        lines.append(f"{grade} (장비 레벨: {lvl})")

    # --- Grade bonus ---
    for _ in range(30):
        stat = random.choice(['최대 생명력', '보너스 대미지', '최대대미지', '크리티컬', '최대 마나'])
        pct = f"{rand_int(1, 50)}.{rand_int(0, 9)}%"
        lo = f"{rand_int(1, 30)}.{rand_int(0, 9)}%"
        lines.append(f"{stat} {pct} 증가 ({lo}~{pct})")
    for _ in range(20):
        lines.append(f"등급 보너스 대미지 {rand_int(10, 50)}.{rand_int(0, 9)}% 증가 ({rand_int(10, 30)}.{rand_int(0, 9)}%~{rand_int(30, 50)}.{rand_int(0, 9)}%)")

    # --- Ergo lines ---
    ergo_grades = ['S', 'A', 'B', 'C']
    for _ in range(20):
        g = random.choice(ergo_grades)
        lines.append(f"등급 {g} ({rand_int(1, 50)}/{rand_int(30, 50)} 레벨)")
    lines.append('(에르그 이전 불가)')
    for _ in range(50):
        lines.append(f"무기 공격력 {rand_int(10, 100)} 증가")
    for _ in range(50):
        lines.append(f"무기 마법 공격력 {rand_int(10, 100)} 증가")
    for _ in range(50):
        lines.append(f"모든 속성 연금술 대미지 {rand_int(10, 100)} 증가")
    for _ in range(50):
        lines.append(f"마리오네트 {rand_int(10, 100)} 증가")
    for _ in range(10):
        lines.append(f"스플래시 반경 {rand_int(100, 500)}cm 증가")

    # --- Artisan lines ---
    artisan_effects = ['방어', '보호', '최대스태미나', '최대생명력', '솜씨', '체력']
    for _ in range(60):
        effect = random.choice(artisan_effects)
        lines.append(f"{effect} {rand_int(1, 30)} 증가")

    # --- Murias holy water (low weight — holywater items are not tradable) ---
    for _ in range(5):
        stat = random.choice(['최대대미지', '최소대미지', '최대생명력', '최대마나'])
        lines.append(f"성수 효과(거래 불가) : {stat} {rand_int(5, 30)} 증가")

    # --- Special effects ---
    for _ in range(20):
        lines.append(f"근접공격 자동방어 확률 : {rand_int(1, 15)}.{rand_int(0, 99):02d}%")
    for _ in range(20):
        lines.append(f"원거리공격 자동방어 확률 : {rand_int(1, 15)}.{rand_int(0, 99):02d}%")
    for _ in range(20):
        lines.append(f"마법공격 자동방어 확률 : {rand_int(1, 15)}.{rand_int(0, 99):02d}%")
    for _ in range(20):
        lines.append(f"대미지 감소율 {rand_int(1, 15)}.{rand_int(0, 99):02d}%")

    # --- Equipment types ---
    armor_path = "data/dictionary/item_type_armor.txt"
    weapon_path = "data/dictionary/item_type_weapon.txt"
    attack_speeds = ['매우느린속도', '느린속도', '보통속도', '빠른속도', '매우빠른속도']
    max_hits = ['1타', '2타', '3타', '4타', '5타', '6타']
    if os.path.exists(armor_path):
        with open(armor_path, 'r', encoding='utf-8') as f:
            for line in f:
                name = line.strip()
                if name:
                    lines.append(name)
    if os.path.exists(weapon_path):
        with open(weapon_path, 'r', encoding='utf-8') as f:
            weapons = [line.strip() for line in f if line.strip()]
        for w in weapons:
            lines.append(w)
            speed = random.choice(attack_speeds)
            if '원거리' in w:
                lines.append(f"{speed} {w}")
            else:
                hit = random.choice(max_hits)
                lines.append(f"{speed} {hit} {w}")

    # --- Ownership (reduced — player names are arbitrary) ---
    for _ in range(5):
        lines.append(f"전용 아이템 (전용 일시 해제)")
    for _ in range(5):
        lines.append(f"남은 전용 해제 가능 횟수 : {rand_int(1, 10)}")

    # --- General number formats (extended to 1000) ---
    lines.extend(_generate_number_formats())

    return lines


def load_dictionaries(dict_paths=None):
    """Load dictionary entries.

    Args:
        dict_paths: list of dictionary file paths (default: DICT_PATHS)
    """
    if dict_paths is None:
        dict_paths = DICT_PATHS

    words = []
    for dict_path in dict_paths:
        if not os.path.exists(dict_path):
            print(f"Warning: Dictionary not found at {dict_path}, skipping.")
            continue
        with open(dict_path, 'r', encoding='utf-8') as f:
            entries = [line.strip() for line in f if line.strip()]
        words.extend(entries)
        print(f"  Loaded {len(entries):5d} entries from {os.path.basename(dict_path)}")
    return words
