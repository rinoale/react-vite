#!/usr/bin/env python3
"""
Generate synthetic training images for OCR model (v2 pipeline).

Images match real line crops from TooltipLineSplitter:
- Rendered at game font size on ~260px canvas (natural height 10-14px)
- Binary only (0/255) matching frontend thresholding
- Full tooltip line patterns via templates, not just dictionary words

Run from project root:
    python3 scripts/generate_training_data.py
"""

import os
import random
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import cv2

# === Configuration ===
FONT_PATH = "data/fonts/mabinogi_classic.ttf"
DICT_PATHS = [
    "data/dictionary/reforge.txt",
    "data/dictionary/enchant.txt",
    "data/dictionary/item_name.txt",
    "data/dictionary/tooltip_general.txt",
]
GT_DIR = "data/sample_images"
OUTPUT_DIR = "backend/train_data"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")

# Real line crop dimensions (from analysis of 235 GT lines):
#   Height: 6-14px (median 10px), two clusters at 7px and 10px
#   Width: 22-269px (median 261px), tooltip width ~262-271px
#   Font size 8 → 8-9px height (matches 7px cluster after padding)
#   Font size 9-11 → 9-13px height (matches 10px cluster)
#   Weighted to include both clusters proportionally
FONT_SIZES = [10, 10, 10, 11, 11, 11]  # Only legible sizes. Height varies by character content.
CANVAS_WIDTH = 260  # Match real tooltip width

# Frontend threshold (from sell.jsx)
FRONTEND_THRESHOLD = 80

# Augmentation
VARIATIONS_PER_LABEL = 3

# === Template generators ===

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


def generate_template_lines():
    """Generate training labels from tooltip line templates."""
    lines = []

    # --- Section headers (repeated for weight — these are short, low-height crops) ---
    # Reps are tuned per header based on observed recognition failure rate.

    # Critical: '세공' fails on 3/4 test images → heavy boost
    for _ in range(100):
        lines.append('세공')
    for _ in range(30):
        lines.append('- 세공 -')

    # Critical: '에르그' shows 0 lines despite being detected → boost
    for _ in range(60):
        lines.append('에르그')
    for _ in range(20):
        lines.append('- 에르그 -')

    # Already boosted in A15 — keep
    for _ in range(40):
        lines.append('아이템 속성')
    for _ in range(5):
        lines.append('- 아이템 속성 -')
    for _ in range(40):
        lines.append('아이템 색상')
    for _ in range(5):
        lines.append('- 아이템 색상 -')

    # Moderate boost for remaining headers (currently 10 reps, detection decent)
    for _ in range(30):
        lines.append('인챈트')
    for _ in range(10):
        lines.append('- 인챈트 -')
    for _ in range(30):
        lines.append('개조')
    for _ in range(10):
        lines.append('- 개조 -')

    # Low-frequency headers — keep at baseline
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

    # --- Color part sub-segments (after horizontal splitting) ---
    # The splitter splits "파트 B    R:187 G:153 B:85" into 4 crops:
    #   "파트 B", "R:187", "G:153", "B:85"
    # OCR never sees the full line, so only sub-segments are trained.
    for _ in range(100):
        part = random.choice(['A', 'B', 'C', 'D', 'E', 'F'])
        lines.append(f"파트 {part}")
    for _ in range(150):
        channel = random.choice(['R', 'G', 'B'])
        lines.append(f"{channel}:{rand_rgb()}")
    # Also with colon-space variants OCR might see
    for _ in range(50):
        channel = random.choice(['R', 'G', 'B'])
        lines.append(f"{channel}: {rand_rgb()}")

    # --- Enchant headers ---
    enchant_names = [
        '사라진', '궤적', '충격을', '흡수해 낸', '판타스틱', '성단',
        '새끼너구리', '인챈트 부여 가능',
        '마법의', '치명적인', '불사의', '황금', '은빛',
        '그림자', '빛나는', '날카로운', '강인한', '민첩한',
    ]
    for _ in range(100):
        prefix = random.choice(['접두', '접미'])
        name = random.choice(enchant_names)
        rank = rand_rank()
        lines.append(f"[{prefix}] {name} (랭크 {rank})")

    # --- Enchant effects (- prefix) ---
    # Boosted to 500 reps — '- ' prefix consistently misread as '소' in inference.
    # More examples give the model more exposure to the dash character in context.
    effect_words = ['수리비', '보호', '방어', '최대생명력', '최대마나', '최대스태미나',
                    '최대대미지', '최소대미지', '대미지밸런스', '마법 공격력',
                    '마법 보호', '크리티컬', '마리오네트 최대 대미지']
    for _ in range(500):
        effect = random.choice(effect_words)
        val = rand_int(1, 100)
        change = random.choice(['증가', '감소'])
        lines.append(f"- {effect} {val} {change}")

    # --- Enchant effects with range ---
    for _ in range(50):
        effect = random.choice(effect_words)
        lo = rand_int(1, 50)
        hi = rand_int(lo, lo + 30)
        lines.append(f"- {effect} {hi} 증가 ({lo}~{hi})")

    # --- Enchant with condition ---
    skills = ['회피', '파이널 히트', '윈드밀', '돌진', '다운 어택', '레이지 임팩트',
              '연금술 마스터리', '엘리멘탈 웨이브', '탐험 레벨이']
    for _ in range(100):
        skill = random.choice(skills)
        rank = random.choice(['1', '6', '9', 'A', 'B', '15'])
        effect = random.choice(effect_words)
        val = rand_int(1, 60)
        lines.append(f"- {skill} 랭크 {rank} 이상일 때 {effect} {val} 증가")

    # --- Misc enchant lines ---
    for _ in range(30):
        lines.append(f"- 수리비 {rand_pct()} {random.choice(['증가', '감소'])}")
    lines.extend(['- 인챈트 추출 불가', '- 약해보임',
                  '- 불 속성', '- 얼음 속성', '- 번개 속성'])

    # --- Sub-bullets (ㄴ marker, no leading spaces) ---
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
        lines.append(f"ㄴ {effect} {sign}{val}{unit}")

    # More sub-bullet patterns
    # Note: '대미지 배율' uses no space before % (confirmed from GT: "72% 증가")
    for _ in range(50):
        lines.append(f"ㄴ 대미지 배율 {rand_int(10, 150)}% 증가")
    # Note: '쿨타임 감소' uses no space before 초 (confirmed from GT: "7.60초 감소")
    for _ in range(50):
        lines.append(f"ㄴ 쿨타임 감소 {rand_int(1, 15)}.{rand_int(0, 99):02d}초 감소")
    # Some enchant effects DO use space before % (대미지, 최소부상률, 지속대미지)
    for _ in range(50):
        effect = random.choice(['대미지', '최소부상률', '지속대미지'])
        lines.append(f"ㄴ {effect} {rand_int(1, 200)} % 증가")

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
        lines.append(f"- {name}{n}")
    for _ in range(50):
        name = random.choice(reforge_names)
        n = rand_int(1, 4)
        lines.append(f"- {name} {n}")

    # --- Crafting lines (세공) ---
    craft_skills = ['클로저 대미지 배율', '크로스 버스터 대미지 배율',
                    '파이어 매직 실드 쿨타임 감소', '스매시 대미지',
                    '최소부상률', '멜로디 쇼크 지속대미지', '최대 공격력']
    for _ in range(50):
        skill = random.choice(craft_skills)
        lines.append(f"- {skill}({rand_level()} 레벨)")
    for _ in range(50):
        skill = random.choice(craft_skills)
        lines.append(f"- {skill}({rand_level()} 레벨)")

    # --- Set item lines ---
    set_skills = ['돌진', '스매시', '윈드밀', '파이널 히트', '파이널 스트라이크']
    for _ in range(50):
        skill = random.choice(set_skills)
        n = rand_int(1, 10)
        lines.append(f"- {skill} 강화 +{n}")
    for _ in range(50):
        skill = random.choice(set_skills)
        lines.append(f"- {skill} 강화 +{rand_int(1, 10)}")

    lines.extend([
        f"발동 조건: 강화 수치 {rand_int(5, 15)} 달성" for _ in range(20)
    ])

    # --- Piercing ---
    for _ in range(30):
        lvl = rand_int(1, 5)
        lines.append(f"- 피어싱 레벨 {lvl}")
    for _ in range(30):
        lvl = rand_int(1, 5)
        extra = random.choice(['', f'+ {rand_int(1,3)}'])
        lines.append(f"- 피어싱 레벨 {lvl}{extra}")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"- 방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"- 마법 방어 {d}, 마법 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  ㄴ 방어 {d}, 보호 {p} 차감")
    for _ in range(20):
        d, p = rand_int(5, 50), rand_int(5, 30)
        lines.append(f"  ㄴ 마법 방어 {d}, 마법 보호 {p} 차감")

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
    # GT format uses colon: "마스터 (장비 레벨: 65)" — must match with colon
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
        lines.append(f"- 무기 공격력 {rand_int(10, 100)} 증가")
    for _ in range(10):
        lines.append(f"- 스플래시 반경 {rand_int(100, 500)}cm 증가")

    # --- Special reforging ---
    for _ in range(20):
        lines.append(f"- 크리티컬 대미지 : {rand_int(100, 200)} +{rand_int(10, 80)}%")

    # --- Artisan lines ---
    artisan_effects = ['방어', '보호', '최대스태미나', '최대생명력', '솜씨', '체력']
    for _ in range(60):
        effect = random.choice(artisan_effects)
        lines.append(f"- {effect} {rand_int(1, 30)} 증가")

    # --- Holy water / special effects ---
    for _ in range(20):
        stat = random.choice(['최대대미지', '최소대미지', '최대생명력', '최대마나'])
        lines.append(f"- 성수 효과(거래 불가) : {stat} {rand_int(5, 30)} 증가")
    for _ in range(20):
        lines.append(f"- 근접공격 자동방어 확률 : {rand_int(1, 15)}.{rand_int(0, 99):02d}%")

    # --- Prefix-stripped variants ---
    # The splitter sometimes crops away leading "- " or "ㄴ ",
    # so we train on content-only versions too.
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


def load_gt_lines():
    """Load all non-empty lines from *_expected.txt ground truth files.

    Uses _expected.txt (user-maintained, clean prefixes, no bottom area) rather
    than _processed.txt (has outdated . prefixes and full color part lines).

    Color part lines (파트 X R:N G:N B:N) are excluded — the splitter breaks
    these into sub-segments that OCR never sees as a full line. Sub-segment
    templates (파트 A/B/C, R:N, G:N, B:N) are generated by generate_template_lines().
    """
    import re
    gt_lines = []
    if not os.path.exists(GT_DIR):
        return gt_lines
    for f in os.listdir(GT_DIR):
        if not f.endswith('_expected.txt'):
            continue
        with open(os.path.join(GT_DIR, f), 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                # Skip full color part lines — OCR only ever sees sub-segments
                if re.match(r'^-?\s*파트\s+[A-F]', line):
                    continue
                # Skip comment lines added by regenerate_gt.py
                if line.startswith('#'):
                    continue
                gt_lines.append(line)
    return list(set(gt_lines))


def load_dictionaries():
    """Load dictionary entries."""
    words = []
    for dict_path in DICT_PATHS:
        if not os.path.exists(dict_path):
            print(f"Warning: Dictionary not found at {dict_path}, skipping.")
            continue
        with open(dict_path, 'r', encoding='utf-8') as f:
            entries = [line.strip() for line in f if line.strip()]
        words.extend(entries)
    return words


def render_line(text, font_size, canvas_width):
    """Render a single text line, tight-cropped to ink bounds + padding.

    Matches how TooltipLineSplitter crops real images: horizontal ink bounds
    with pad_x = max(2, h//3), pad_y = max(1, h//5).

    Returns (PIL Image in mode 'L', bool success).
    Image height is natural (not resized to 32px).
    """
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        return None, False

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if text_w <= 0 or text_h <= 0:
        return None, False

    # Padding matches splitter formula: pad_y = max(1, h//5), pad_x = max(2, h//3)
    pad_y = max(1, text_h // 5)
    pad_x = max(2, text_h // 3)
    img_h = text_h + 2 * pad_y

    # Tight-crop to text width + padding, matching splitter's ink-bounds cropping.
    # Real crops: short text like "천옷" → crop_w=22px, long text → crop_w=258px.
    img_w = text_w + 2 * pad_x

    img = Image.new('L', (img_w, img_h), color=255)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x, pad_y - bbox[1]), text, font=font, fill=0)

    # Binary thresholding (no blur — real crops are clean binary from frontend)
    thresh = FRONTEND_THRESHOLD + random.randint(-5, 20)
    img = img.point(lambda x: 0 if x < thresh else 255, 'L')

    return img, True


# --- Image quality gates (applied to every image) ---
MIN_INK_RATIO = 0.02    # At least 2% of pixels must be ink (black)
MIN_WIDTH = 10           # Minimum image width in pixels
MIN_HEIGHT = 8           # Minimum image height in pixels


def split_long_label(text, font, max_width):
    """Split a label at word boundaries if it exceeds max_width pixels.

    Returns a list of sub-labels. If the text fits, returns [text].
    Splits at spaces to produce sub-labels that each fit within max_width.
    """
    bbox = font.getbbox(text)
    if bbox[2] - bbox[0] <= max_width:
        return [text]

    words = text.split(' ')
    parts = []
    current = words[0]
    for word in words[1:]:
        candidate = current + ' ' + word
        bbox = font.getbbox(candidate)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            parts.append(current)
            current = word
    parts.append(current)
    return parts


def split_all_labels(labels, font_path, max_font_size, max_width):
    """Split all labels that would overflow at the largest font size."""
    font = ImageFont.truetype(font_path, max_font_size)
    result = []
    split_count = 0
    for label in labels:
        parts = split_long_label(label, font, max_width)
        if len(parts) > 1:
            split_count += 1
        result.extend(parts)
    if split_count > 0:
        print(f"  Split {split_count} long labels into {len(result) - len(labels) + split_count} sub-labels")
    return result


def generate_data():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    # Collect all labels
    all_labels = []

    # 1. Template-generated lines
    template_lines = generate_template_lines()
    print(f"Template lines: {len(template_lines)}")

    # 2. Ground truth lines (verbatim)
    gt_lines = load_gt_lines()
    print(f"Ground truth lines: {len(gt_lines)}")

    # 3. Dictionary entries
    dict_words = load_dictionaries()
    print(f"Dictionary entries: {len(dict_words)}")

    # Combine (deduplicate)
    all_labels = list(set(template_lines + gt_lines + dict_words))

    # Split long labels at word boundaries to fit within canvas
    max_font = max(FONT_SIZES)
    max_text_width = CANVAS_WIDTH - 2 * max(2, 11 // 3)  # canvas minus padding at largest font
    all_labels = split_all_labels(all_labels, FONT_PATH, max_font, max_text_width)
    all_labels = list(set(all_labels))  # deduplicate after splitting
    random.shuffle(all_labels)
    print(f"Unique labels: {len(all_labels)}")

    count = 0
    skipped = 0

    for label in all_labels:
        for v in range(VARIATIONS_PER_LABEL):
            font_size = random.choice(FONT_SIZES)

            # Vary canvas width slightly
            cw = CANVAS_WIDTH + random.randint(-10, 10)

            img, ok = render_line(label, font_size, cw)
            if not ok:
                skipped += 1
                continue

            # Quality gates: reject any image that isn't clearly readable
            arr = np.array(img)
            ink_ratio = (arr == 0).sum() / arr.size if arr.size > 0 else 0
            img_w_actual, img_h_actual = img.size

            if len(np.unique(arr)) < 2:
                skipped += 1
                continue
            if ink_ratio < MIN_INK_RATIO:
                skipped += 1
                continue
            if img_w_actual < MIN_WIDTH or img_h_actual < MIN_HEIGHT:
                skipped += 1
                continue

            # Convert to RGB (EasyOCR expects 3 channels)
            img_rgb = img.convert('RGB')

            filename = f"syn_{count:06d}"
            img_rgb.save(os.path.join(IMAGES_DIR, f"{filename}.png"))
            with open(os.path.join(LABELS_DIR, f"{filename}.txt"), 'w', encoding='utf-8') as f:
                f.write(label)

            count += 1
            if count % 5000 == 0:
                print(f"  Generated {count} images...")

    print(f"\nDone! Generated {count} images ({skipped} skipped)")
    print(f"Output: {OUTPUT_DIR}")

    # Full verification on ALL images (not sampling)
    print("\nVerifying ALL images...")
    all_files = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png')]
    failures = {'non_binary': 0, 'low_ink': 0, 'too_small': 0}
    for f in all_files:
        img = Image.open(os.path.join(IMAGES_DIR, f))
        arr = np.array(img)
        if len(arr.shape) == 3:
            arr = arr[:, :, 0]

        unique = set(np.unique(arr))
        if unique - {0, 255}:
            failures['non_binary'] += 1

        ink_ratio = (arr == 0).sum() / arr.size if arr.size > 0 else 0
        if ink_ratio < MIN_INK_RATIO:
            failures['low_ink'] += 1

        w, h = img.size
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            failures['too_small'] += 1

    total_failures = sum(failures.values())
    if total_failures == 0:
        print(f"  ALL {len(all_files)} images PASSED (binary, ink>{MIN_INK_RATIO:.0%}, w>={MIN_WIDTH}, h>={MIN_HEIGHT})")
    else:
        print(f"  FAILURES in {len(all_files)} images: {failures}")


if __name__ == "__main__":
    generate_data()
