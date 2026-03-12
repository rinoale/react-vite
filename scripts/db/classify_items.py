#!/usr/bin/env python3
"""Classify all items in item_name.txt into item.yaml with tags.

Uses keyword patterns from item_type_weapon.txt and item_type_armor.txt
plus heuristic rules for non-equipment items.
"""

import re
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEM_NAME_FILE = ROOT / "data/source_of_truth/item_name.txt"
ITEM_YAML_FILE = ROOT / "data/source_of_truth/typed_item.yaml"      # existing hand-curated (read-only)
ITEM_OUTPUT_FILE = ROOT / "data/source_of_truth/item_classified.yaml"  # output


# ── Priority-ordered classification rules ──
# Each rule: (tag, pattern_func)
# First match wins. Order matters — more specific patterns before general ones.

def _build_rules():
    """Build classification rules. Returns list of (tag, match_func) tuples."""

    rules = []

    def keyword(tag, *patterns):
        """Match if any pattern appears in the item name."""
        def match(name):
            return any(p in name for p in patterns)
        rules.append((tag, match))

    def regex(tag, pattern):
        """Match if regex pattern matches the item name."""
        compiled = re.compile(pattern)
        def match(name):
            return bool(compiled.search(name))
        rules.append((tag, match))

    def suffix(tag, *suffixes):
        """Match if name ends with any of the suffixes."""
        def match(name):
            return any(name.endswith(s) for s in suffixes)
        rules.append((tag, match))

    # ── 1. Non-equipment (most specific patterns first) ──

    keyword("정령 변환",         "정령 형상변환 리큐르")
    keyword("이펙트 변경",       "이펙트 변경 카드")
    keyword("외형 변경",         "외형 주문서")
    keyword("제스처",            "제스처 카드")
    keyword("타이틀",            "타이틀 획득 쿠폰")
    keyword("뷰티 쿠폰",        "뷰티 쿠폰")
    keyword("펫",               "호루라기")
    keyword("헤일로",            "헤일로")
    keyword("날개",              "날개", "윙")
    keyword("농장",              "낭만 농장", "하우징")
    keyword("에코스톤",          "에코스톤")
    keyword("토템",              "토템")
    keyword("액션 쿠폰",         "액션 쿠폰")
    keyword("말풍선",            "말풍선 스티커")
    keyword("인형 가방",         "인형 가방")
    keyword("스타더스트",        "스타더스트의 형상")
    keyword("통행증",            "통행증")
    keyword("대미지 스킨",       "대미지 스킨")

    # Cosmetic accessories
    keyword("가발",              "가발", "헤어")
    keyword("얼굴 장식",         "얼굴 장식 슬롯 전용")
    keyword("망토",              "망토", "케이프", "클로크")
    keyword("가방",              "가방", "백팩", "트렁크")
    keyword("꼬리",              "꼬리")
    keyword("머리띠",            "머리띠")
    keyword("우산",              "우산")

    # ── 2. Equipment — weapons ──
    # Specific compound names first, then suffixes

    # Ranged
    keyword("원거리 석궁",       "크로스보우", "석궁")
    keyword("원거리 활",         "보우", "롱 보우", "숏 보우")
    keyword("원거리 수리검",     "수리검", "스로잉 스타")
    keyword("원거리 아틀라틀",   "아틀라틀")
    keyword("듀얼건",            "듀얼건")

    # Two-handed — compound keywords
    keyword("양손 검",           "양손 검", "블레이드", "클레이모어", "투핸디드 소드", "비펜니스")
    keyword("양손 도끼",         "양손 도끼", "배틀 액스", "워리어 액스")
    keyword("양손 둔기",         "양손 둔기", "워리어 해머", "워 해머")

    # One-handed — compound keywords + generic suffix
    keyword("한손 검",           "한손 검", "소드", "레이피어", "글라디우스", "세이버")
    keyword("한손 도끼",         "한손 도끼", "액스", "해쳇")
    keyword("한손 둔기",         "한손 둔기", "해머", "메이스", "모닝스타", "몽둥이")

    # Magic / special
    keyword("스태프",            "스태프")
    keyword("트라이볼트 원드",   "트라이볼트 원드")
    keyword("파이어 원드",       "파이어 원드")
    keyword("아이스 원드",       "아이스 원드")
    keyword("라이트닝 원드",     "라이트닝 원드")
    keyword("힐링 원드",         "힐링 원드")
    regex("원드",                r"원드$")
    keyword("실린더",            "실린더")
    keyword("핸들",              "핸들")
    keyword("마도서",            "마도서", "그리모어")
    keyword("오브",              "오브")
    keyword("체인 블레이드",     "체인 블레이드")
    keyword("대형 낫",           "사이드")
    keyword("랜스",              "랜스")
    keyword("너클",              "너클")
    keyword("악기",              "리라", "류트", "만돌린", "플루트", "우쿨렐레",
            "실로폰", "핸드벨", "전자 기타", "마이크", "샬루모", "드럼")

    # Korean suffix weapons (bare 검, 도끼, 활 at end of name)
    regex("한손 검",             r"검$")
    regex("한손 도끼",           r"도끼$")
    regex("원거리 활",           r"활$")
    keyword("원거리 활",         "화살")

    # ── 3. Shields ──
    keyword("방패",              "실드", "가드실린더", "바클러", "의 방패")

    # ── 4. Heavy armor ──
    keyword("중갑 투구",         "중갑 투구", "풀 헬름", "헤드기어")
    keyword("중갑 건틀렛",       "중갑 건틀렛")
    keyword("중갑 신발",         "중갑 신발", "그리브")
    keyword("중갑옷",            "중갑옷", "플레이트 아머", "풀 플레이트", "체인메일")

    # ── 5. Armor / clothing ──
    keyword("모자",              "모자", "써클릿", "헬멧", "캡", "화관",
            "투구", "비앙카", "서클릿", "헤드밴드", "두건", "베레모", "왕관",
            "족두리", "머리장식", "머리 장식", "헬름")
    keyword("장갑",              "장갑", "건틀렛", "글러브", "손 장식", "팔찌",
            "뱀브레이스")
    keyword("신발",              "부츠", "신발", "슈즈", "구두", "샌들", "테니스화",
            "플랫슈즈", "스니커즈", "운동화", "슬리퍼", "단화")
    regex("신발",                r"힐\(")
    keyword("경갑옷",            "경갑옷", "라멜라 아머")
    keyword("천옷",              "로브", "튜닉")
    keyword("액세서리",          "귀걸이", "목걸이", "반지", "팬던트", "브로치",
            "벨트", "서클 이어링")

    # ── 6. Generic clothing / costume ──
    keyword("의상",              "의상", "의복", "교복", "수트", "드레스", "웨어",
            "코트", "정복", "예복", "턱시도", "유니폼", "한복", "기모노",
            "자켓", "셔츠", "스커트", "팬츠", "바지", "아머", "갑옷",
            "타이츠", "레깅스", "원피스", "정장", "전투복", "캐주얼",
            "가디건", "조끼", "앞치마", "베스트", "파카",
            "후드", "점퍼", "패딩", "수영복", "비키니", "수영복",
            "나이트브링어")

    # ── 7. Consumables ──
    keyword("포션",              "포션")
    keyword("음식",              "스튜", "찌개", "구이", "볶음", "쿠키", "케이크",
            "파이", "빵", "두부", "국수", "비스킷", "초콜릿", "사탕",
            "주스", "밀크", "피자", "샐러드", "수프", "라면", "만두",
            "샌드위치", "카레", "푸딩", "팝콘", "와플", "마카롱",
            "어묵", "떡볶이", "튀김", "치즈", "소시지", "부리또", "머핀",
            "오믈렛", "은붕어", "바닷가재", "소라", "피칸", "달고나",
            "아이스크림", "마시멜로", "전골", "절임", "냉채", "초코볼",
            "밀크티", "하이볼", "칵테일", "모찌", "떡", "잼",
            "타코", "도넛", "크레이프", "탕", "볶음밥", "덮밥",
            "꼬치", "젤리", "캔디", "크림", "밀키트", "요거트",
            "스테이크", "송편", "향초", "과자")
    keyword("허브",              "허브", "약초", "맨드레이크", "로즈힙")
    keyword("염색",              "염색", "염료")

    # ── 8. Materials / resources ──
    keyword("보석",              "아쿠아마린", "다이아몬드", "루비", "사파이어",
            "에메랄드", "자수정", "토파즈", "진주", "만월석",
            "오팔", "가넷", "탄자나이트", "바리사이트")
    keyword("재료",              "가죽끈", "옷감", "실크", "동판", "철판",
            "볼트", "나사", "조각", "추출액", "영양제",
            "결정", "파편", "장작", "겉껍질", "깃털",
            "광목", "구조체", "얼음", "금괴")
    keyword("광석",              "광석", "원석")

    # ── 9. Furniture / homestead ──
    keyword("가구",              "의자", "소파", "침대", "선베드", "카페트",
            "조명", "테이블", "천막", "트리", "화덕", "텐트",
            "모래성", "야영지", "이젤", "책상", "세트(")

    # ── 10. Other types ──
    keyword("퍼핏",              "퍼핏", "피니 펫")
    keyword("인형",              "인형", "피규어", "미니어처")
    keyword("안경",              "안경", "선글라스")
    keyword("마스크",            "마스크", "가면")
    keyword("설계도",            "설계도")
    keyword("콘서트 용품",       "야광봉", "콘서트용")
    keyword("부채",              "부채")
    keyword("장식",              "장식")
    keyword("주문서",            "주문서")
    keyword("스크롤",            "스크롤")
    keyword("쿠폰",              "쿠폰")
    keyword("상자",              "상자", "박스")
    keyword("카드",              "카드")
    keyword("풍선",              "풍선")

    return rules


def classify(name, rules):
    """Classify an item name using priority-ordered rules."""
    for tag, match_fn in rules:
        if match_fn(name):
            return tag
    return "misc"


def main():
    # Load existing item.yaml (skip if broken/unreadable)
    existing = {}
    if ITEM_YAML_FILE.exists():
        try:
            with open(ITEM_YAML_FILE) as f:
                data = yaml.safe_load(f) or []
            for item in data:
                existing[item["name"]] = item.get("tags", [])
        except yaml.YAMLError:
            print("Warning: existing item.yaml is broken, reclassifying all items")

    # Load all item names
    with open(ITEM_NAME_FILE) as f:
        all_names = [line.strip() for line in f if line.strip()]

    rules = _build_rules()

    # Classify
    results = []
    tag_counts = {}
    for name in all_names:
        if name in existing:
            tags = existing[name]
        else:
            tag = classify(name, rules)
            tags = [tag]
        results.append({"name": name, "tags": tags})
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    # Write output (quote names that contain YAML-special chars)
    def _quote(s):
        if any(c in s for c in ":{}[]&*?|>',\"#%@`"):
            escaped = s.replace("'", "''")
            return f"'{escaped}'"
        return s

    with open(ITEM_OUTPUT_FILE, "w") as f:
        for item in results:
            f.write(f"- name: {_quote(item['name'])}\n")
            f.write(f"  tags:\n")
            for tag in item["tags"]:
                f.write(f"  - {tag}\n")

    # Print summary
    print(f"Total items: {len(results)}")
    print(f"Existing (kept): {sum(1 for n in all_names if n in existing)}")
    print(f"\nTag distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"  {tag:20s} {count:5d}")


if __name__ == "__main__":
    main()
