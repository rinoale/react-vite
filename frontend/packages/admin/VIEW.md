# Admin Views

## App Layout

Single full-page view, no sidebar or router. Renders `<Admin />` directly.

---

## / — Admin Dashboard

```
+--header----------------------------------------------------------+
| ADMIN DASHBOARD              [Enchants] [Effects] [Links] [Items]|
| Database Validation           1,234      5,678    9,012    42    |
+------------------------------------------------------------------+
|                                                                  |
|  [Enchants] [Items] [Corrections]   ← tab bar                   |
|                                                                  |
+------------------------------------------------------------------+
```

### Tab: Enchants

```
+--ENCHANT ENTRIES-------------------------------------------------+
| [list] ENCHANT ENTRIES    [search___] [PREV] 1-100/1234 [NEXT] @|
+------------------------------------------------------------------+
| > [PREFIX] 관리자  Rank A                   ID: 42   6 EFFECTS   |
|------------------------------------------------------------------+
| v [SUFFIX] 곰의   Rank 9                   ID: 87   4 EFFECTS   |
|   +--Enchant Effects & Conditions---------------------------+    |
|   | - 최대대미지 5 ~ 10 증가               [Increase]       |    |
|   |   Condition: 양손검 장착 시                              |    |
|   |   Order: 1  Range: 5 ~ 10                               |    |
|   | - 방어력 3 감소                        [Decrease]        |    |
|   |   Order: 2  Range: -3 ~ -3                              |    |
|   +----------------------------------------------------------+    |
| > [PREFIX] 야생의  Rank 7                   ID: 103  5 EFFECTS   |
+------------------------------------------------------------------+
```

- **Enchant row**: click to expand/collapse effects
- **Slot badge**: blue=Prefix, red=Suffix
- **Effect tone**: blue=increase, red=decrease
- **Pagination**: server-side, 100 per page
- **Search**: client-side filter on enchant name

### Tab: Corrections

```
+--OCR CORRECTIONS-------------------------------------------------+
| [img] OCR CORRECTIONS       [pending|approved] [PREV] 1-50 [NEXT] @|
+------------------------------------------------------------------+
| [crop-img]  original-text → corrected-text                       |
|             [enchant] [model] 95.2%  [FM]         ID: 7          |
|                                              [pencil] [Approve]  |
|------------------------------------------------------------------+
| [crop-img]  original-text → corrected-text                       |
|             [item_attrs] [model] 82.1%            ID: 8          |
|                                              [pencil] [Approve]  |
+------------------------------------------------------------------+
```

- **Crop image**: pixelated line crop from OCR session
- **Inline edit**: click pencil → input replaces corrected text, Enter saves
- **Approve**: marks correction as approved, removes from pending list
- **Badges**: section (purple), model (mono), FM (yellow), charset mismatch (red)

### Tab: Items

```
+--REGISTERED ITEMS----------------------------------------------+
| [pkg] REGISTERED ITEMS             [PREV] 1-50 [NEXT] @       |
+------------------------------------------------------------------+
| 라이트 레더 아머                           2026-02-26   ID: 3    |
|                                            2 ENCHANTS            |
|------------------------------------------------------------------+
| 캡틴 수트                                  2026-02-25   ID: 2    |
|------------------------------------------------------------------+
| 타이탄 블레이드                             2026-02-24   ID: 1    |
|                                            1 ENCHANT             |
+------------------------------------------------------------------+
```

- **Flat list**: no expand/collapse, simpler than enchants
- **Enchant badge**: shown only if enchant_count > 0
- **Pagination**: server-side, 50 per page, newest first
- **Timestamp**: created_at formatted as locale string
