"""Shared template generators for OCR training data.

Extracted from scripts/ocr/general_model/generate_training_data.py.
Both font-specific generators import from here to avoid duplication.
"""

import os
import random

# Dictionary paths (relative to project root)
DICT_PATHS = [
    "data/dictionary/reforge.txt",
    "data/dictionary/enchant_effect.txt",
    "data/dictionary/tooltip_general.txt",
]

# Post-dedup boost for critical section headers.
# Each header gets proportionally more training images.
HEADER_BOOSTS = [
    ('세공',         43),
    ('- 세공 -',      9),
    ('에르그',        26),
    ('- 에르그 -',    6),
    ('인챈트',         9),
    ('- 인챈트 -',    3),
    ('아이템 속성',   12),
    ('아이템 색상',   12),
    ('개조',           9),
    ('- 개조 -',      3),
]


def rand_int(lo, hi):
    return random.randint(lo, hi)


def rand_stat():
    return rand_int(0, 300)


def rand_pct():
    return f"{rand_int(1, 200)}%"


def rand_durability():
    mx = rand_int(5, 50)
    cur = rand_int(0, mx)
    return f"{cur}/{mx}"


def rand_rgb():
    return rand_int(0, 255)


def rand_level():
    mx = rand_int(3, 20)
    cur = rand_int(1, mx)
    return f"{cur}/{mx}"


def rand_rank():
    return random.choice(['1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', 'S'])


def rand_float():
    return f"{rand_int(1, 99)}.{rand_int(0, 9)}%"


def generate_template_lines(bullet='.', subbullet='ㄴ'):
    """Generate training labels from tooltip line templates.

    Args:
        bullet: first-level sub-bullet character (from training config)
        subbullet: second-level sub-bullet character (from training config)
    """
    lines = []

    # --- Section headers (repeated for weight) ---
    for _ in range(100):
        lines.append('세공')
    for _ in range(30):
        lines.append('- 세공 -')

    for _ in range(60):
        lines.append('에르그')
    for _ in range(20):
        lines.append('- 에르그 -')

    for _ in range(40):
        lines.append('아이템 속성')
    for _ in range(5):
        lines.append('- 아이템 속성 -')
    for _ in range(40):
        lines.append('아이템 색상')
    for _ in range(5):
        lines.append('- 아이템 색상 -')

    for _ in range(30):
        lines.append('인챈트')
    for _ in range(10):
        lines.append('- 인챈트 -')
    for _ in range(30):
        lines.append('개조')
    for _ in range(10):
        lines.append('- 개조 -')

    misc_headers = ['세트아이템', '장인 개조', '등급', '에픽', '레어', '마스터',
                    '전용 해제', '기본 효과', '추가 효과', '최종 단계 개방 완료',
                    '- 세트아이템 -']
    for h in misc_headers:
        for _ in range(10):
            lines.append(h)

    # --- Stat lines ---
    for _ in range(200):
        stat = random.choice(['방어력', '보호', '공격', '크리티컬', '밸런스', '최대대미지', '최소대미지'])
        lines.append(f"{stat} {rand_stat()}")

    for _ in range(300):
        lines.append(f"내구력 {rand_durability()}")

    for _ in range(50):
        lines.append(f"공격 {rand_int(10, 300)}~{rand_int(50, 500)}")

    for _ in range(50):
        lines.append(f"부상률 {rand_int(10, 80)}~{rand_int(50, 100)}%")

    for _ in range(50):
        lines.append(f"크리티컬 {rand_int(1, 100)}%")

    for _ in range(50):
        lines.append(f"밸런스 {rand_int(10, 100)}%")

    # --- Color part sub-segments ---
    for _ in range(100):
        part = random.choice(['A', 'B', 'C', 'D', 'E', 'F'])
        lines.append(f"파트 {part}")
    for _ in range(150):
        channel = random.choice(['R', 'G', 'B'])
        lines.append(f"{channel}:{rand_rgb()}")
    for _ in range(50):
        channel = random.choice(['R', 'G', 'B'])
        lines.append(f"{channel}: {rand_rgb()}")

    # NOTE: Enchant headers like "[접두] 사라진 (랭크 5)" are handled by
    # the enchant_header model, not content OCR. Not included here.

    # --- Enchant effects (. prefix) ---
    effect_words = ['수리비', '보호', '방어', '최대생명력', '최대마나', '최대스태미나',
                    '최대대미지', '최소대미지', '대미지밸런스', '마법 공격력',
                    '마법 보호', '크리티컬', '마리오네트 최대 대미지']
    for _ in range(500):
        effect = random.choice(effect_words)
        val = rand_int(1, 100)
        change = random.choice(['증가', '감소'])
        lines.append(f"{bullet} {effect} {val} {change}")

    # --- Enchant effects with range ---
    for _ in range(50):
        effect = random.choice(effect_words)
        lo = rand_int(1, 50)
        hi = rand_int(lo, lo + 30)
        lines.append(f"{bullet} {effect} {hi} 증가 ({lo}~{hi})")

    # --- Enchant with condition ---
    skills = ['회피', '파이널 히트', '윈드밀', '돌진', '다운 어택', '레이지 임팩트',
              '연금술 마스터리', '엘리멘탈 웨이브', '탐험 레벨이']
    for _ in range(100):
        skill = random.choice(skills)
        rank = random.choice(['1', '6', '9', 'A', 'B', '15'])
        effect = random.choice(effect_words)
        val = rand_int(1, 60)
        lines.append(f"{bullet} {skill} 랭크 {rank} 이상일 때 {effect} {val} 증가")

    # --- Misc enchant lines ---
    for _ in range(30):
        lines.append(f"{bullet} 수리비 {rand_pct()} {random.choice(['증가', '감소'])}")
    lines.extend([f'{bullet} 인챈트 추출 불가', f'{bullet} 약해보임',
                  f'{bullet} 불 속성', f'{bullet} 얼음 속성', f'{bullet} 번개 속성'])

    # --- Sub-bullets (ㄴ marker) ---
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
        lines.append(f"{subbullet} {effect} {sign}{val}{unit}")

    for _ in range(50):
        lines.append(f"{subbullet} 대미지 배율 {rand_int(10, 150)}% 증가")
    for _ in range(50):
        lines.append(f"{subbullet} 쿨타임 감소 {rand_int(1, 15)}.{rand_int(0, 99):02d}초 감소")
    for _ in range(50):
        effect = random.choice(['대미지', '최소부상률', '지속대미지'])
        lines.append(f"{subbullet} {effect} {rand_int(1, 200)} % 증가")

    # --- Reforging headers ---
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

    # --- Reforging effects ---
    reforge_names = ['표면 강화', '경량화', '담금질', '보석 개조']
    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"{bullet} {name}{n}")
    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"{bullet} {name} {n}")

    # --- Crafting lines (세공) ---
    craft_skills = ['클로저 대미지 배율', '크로스 버스터 대미지 배율',
                    '파이어 매직 실드 쿨타임 감소', '스매시 대미지',
                    '최소부상률', '멜로디 쇼크 지속대미지', '최대 공격력']
    for _ in range(50):
        skill = random.choice(craft_skills)
        lines.append(f"{bullet} {skill}({rand_level()} 레벨)")
    for _ in range(50):
        skill = random.choice(craft_skills)
        lines.append(f"{bullet} {skill}({rand_level()} 레벨)")

    # --- Set item lines ---
    set_skills = ['돌진', '스매시', '윈드밀', '파이널 히트', '파이널 스트라이크']
    for _ in range(50):
        skill = random.choice(set_skills)
        n = rand_int(1, 10)
        lines.append(f"{bullet} {skill} 강화 +{n}")
    for _ in range(50):
        skill = random.choice(set_skills)
        lines.append(f"{bullet} {skill} 강화 +{rand_int(1, 10)}")

    lines.extend([
        f"발동 조건: 강화 수치 {rand_int(5, 15)} 달성" for _ in range(20)
    ])

    # --- Piercing ---
    for _ in range(30):
        lvl = rand_int(1, 5)
        lines.append(f"{bullet} 피어싱 레벨 {lvl}")
    for _ in range(30):
        lvl = rand_int(1, 5)
        extra = random.choice(['', f'+ {rand_int(1,3)}'])
        lines.append(f"{bullet} 피어싱 레벨 {lvl}{extra}")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"{bullet} 방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"{bullet} 마법 방어 {d}, 마법 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  {subbullet} 방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  {subbullet} 마법 방어 {d}, 마법 보호 {p} 차감")

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
            '#소유권 보존', '#파트너 선물 및 착용 불가', '#계정 불가']
    for _ in range(50):
        n = rand_int(2, 5)
        selected = random.sample(tags, min(n, len(tags)))
        lines.append(' '.join(selected))

    # --- Price lines ---
    for _ in range(30):
        price = random.choice([f'{rand_int(100, 99999)} 골드', f'{rand_int(1, 99)}만 골드', '판매불가'])
        lines.append(f"상점판매가 : {price}")

    # --- Grade lines ---
    grades = ['마스터', '그랜드마스터', '챔피언', '히어로', '일반', '고급', '레어', '엘리트']
    for _ in range(60):
        grade = random.choice(grades)
        lvl = random.choice([10, 20, 30, 40, 50, 60, 65, 70, 80, 90, 100])
        lines.append(f"{grade} (장비 레벨: {lvl})")

    # --- Grade bonus ---
    for _ in range(30):
        stat = random.choice(['최대 생명력', '보너스 대미지', '최대대미지', '크리티컬'])
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
    lines.extend(['(에르그 이전 불가)'])
    for _ in range(20):
        lines.append(f"{bullet} 무기 공격력 {rand_int(10, 100)} 증가")
    for _ in range(10):
        lines.append(f"{bullet} 스플래시 반경 {rand_int(100, 500)}cm 증가")

    # --- Special reforging ---
    for _ in range(20):
        lines.append(f"{bullet} 크리티컬 대미지 : {rand_int(100, 200)} +{rand_int(10, 80)}%")

    # --- Artisan lines ---
    artisan_effects = ['방어', '보호', '최대스태미나', '최대생명력', '솜씨', '체력']
    for _ in range(60):
        effect = random.choice(artisan_effects)
        lines.append(f"{bullet} {effect} {rand_int(1, 30)} 증가")

    # --- Holy water / special effects ---
    for _ in range(20):
        stat = random.choice(['최대대미지', '최소대미지', '최대생명력', '최대마나'])
        lines.append(f"{bullet} 성수 효과(거래 불가) : {stat} {rand_int(5, 30)} 증가")
    for _ in range(20):
        lines.append(f"{bullet} 근접공격 자동방어 확률 : {rand_int(1, 15)}.{rand_int(0, 99):02d}%")

    # --- Prefix-stripped variants ---
    for _ in range(100):
        effect = random.choice(effect_words)
        val = rand_int(1, 100)
        change = random.choice(['증가', '감소'])
        lines.append(f"{effect} {val} {change}")

    for _ in range(50):
        effect = random.choice(effect_words)
        lo = rand_int(1, 50)
        hi = rand_int(lo, lo + 30)
        lines.append(f"{effect} {hi} 증가 ({lo}~{hi})")

    for _ in range(50):
        skill = random.choice(skills)
        rank = random.choice(['1', '6', '9', 'A', 'B', '15'])
        effect = random.choice(effect_words)
        val = rand_int(1, 60)
        lines.append(f"{skill} 랭크 {rank} 이상일 때 {effect} {val} 증가")

    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"{name}{n}")

    for _ in range(30):
        skill = random.choice(craft_skills)
        lines.append(f"{skill}({rand_level()} 레벨)")

    for _ in range(30):
        skill = random.choice(set_skills)
        n = rand_int(1, 10)
        lines.append(f"{skill} 강화 +{n}")

    for _ in range(30):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"방어 {d}, 보호 {p} 차감")
    for _ in range(30):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"마법 방어 {d}, 마법 보호 {p} 차감")

    for _ in range(20):
        lvl = rand_int(1, 5)
        lines.append(f"피어싱 레벨 {lvl}")

    for _ in range(20):
        lines.append(f"무기 공격력 {rand_int(10, 100)} 증가")
    for _ in range(10):
        lines.append(f"스플래시 반경 {rand_int(100, 500)}cm 증가")

    for _ in range(20):
        effect = random.choice(artisan_effects)
        lines.append(f"{effect} {rand_int(1, 30)} 증가")

    # --- Misc tooltip lines ---
    misc = [
        '인챈트 스크롤과 마법 가루를 사용하여 인챈트를 부여할',
        '수 있습니다.',
        '[장비 세공 도구]를 사용하여 장비를 세공할 수 있습니다.',
        '세공을 하게 되면 [세공 능력치]를 무작위로 부여받을 수 있습니다.',
        '특별 이벤트 장비(거래 불가)',
        'MABINOGI',
        'Copyright (C) 2003 Nexon Corporation. All r',
    ]
    lines.extend(misc)

    # --- Equipment types ---
    types = ['경갑옷', '중갑옷', '천옷', '의복', '로브', '가죽 갑옷', '액세서리',
             '검', '둔기', '도끼', '한손검', '양손검', '너클', '완드', '스태프',
             '보통속도 2타 양손 검', '빠른속도 3타 한손 검']
    lines.extend(types)

    # --- Ownership ---
    for _ in range(20):
        name = random.choice(['아자린', '크로노스', '에밀리', '루카스', '미라벨'])
        lines.append(f"{name} 전용 아이템 (전용 일시 해제)")
    for _ in range(10):
        lines.append(f"남은 전용 해제 가능 횟수 : {rand_int(1, 10)}")

    # --- Appearance change ---
    weapon_names = ['클레이모어', '바스타드 소드', '크레센트', '글래디우스']
    for _ in range(10):
        lines.append(f"외형 변경 아이템 : {random.choice(weapon_names)}")

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
