# Mabinogi Marketplace
## OCR-Powered Item Trading Platform
Screenshot to Listing. Search. Trade. Verify.

---

# What is this?

- **Screenshot → Listing**: Upload a tooltip screenshot, get a fully structured listing. Zero manual entry.
- **Smart Search**: Tags + game item + attribute/option filters. Cascading text search. Saveable presets.
- **Auto-Tag Engine**: Database-driven rules generate tags automatically. No code changes to add rules.
- **In-Game Verification**: OTP via game all-chat. Prove you own the character. Verified badge.
- **Self-Correcting OCR**: User edits become training data. The system improves from usage.

---

# 1. Screenshot → Listing
## 8-stage V3 pipeline processes the original color screenshot

- Stage 1: Border Detection + Crop
- Stage 2: Orange Header Detection (visual, before OCR)
- Stage 3: Segmentation + Section Classification
- Stage 4: Per-Section Content OCR (font-matched readers)
- Stage 5: Item Name Parsing (enchant prefix/suffix split)
- Stage 6: Fuzzy Matching (section-aware correction)
- Stage 7: Structured Rebuild (enchant/reforge/erg data)
- Stage 8: Enchant Resolution (P1/P2/P3 competition)

> Key insight: Detect sections BEFORE OCR → eliminates cascade failures from garbled headers

---

# Dullahan Algorithm
## Effect-guided enchant header correction

- Problem: Header OCR reads tiny crops (55-120px). 폭단 vs 성단 — both valid enchant names.
- Standard fuzzy matching can't help — both candidates score equally.

- **Key Insight**
  - 802/1172 enchants have unique effect signatures.
  - The effect lines (already OCR'd) disambiguate the header.

- **Algorithm**
  - 1. Score all DB entries by header name similarity
  - 2. Take candidates within 15 points of best score
  - 3. For each candidate, score effect lines against DB effects
  - 4. Winner = highest combined (name + effect) score

> Named after the headless horseman — the "body" (effects) finds the correct "head" (header)

---

# 2. Smart Search

- **Search Dimensions (all AND-intersected)**
  - Text query — cascading 3-tier: tags → game items → listing names
  - Tag chips — polymorphic: tag on enchant matches listings with that enchant
  - Game item filter — enables type-specific option panels
  - Attribute filters — damage, balance, defense, erg, special upgrade
  - Option filters — reforge, enchant (per-effect), echostone, murias

- **Saved Search Presets**
  - localStorage JSON, max 20 entries
  - Order-independent dedup via DJB2 hash on sorted params
  - FILTER_KEYS array = single source of truth for all filter types

---

# 3. Auto-Tag Engine
## Database-driven rules. No code changes to add tags.

- **Architecture**
  - Every rule = conditions[] + tag_template
  - 8 operators: ==, !=, >=, <=, >, <, in, contains
  - Column references for cross-field comparison
  - Group-based cross-row matching
  - Runs as BackgroundTask (non-blocking)
  - Rules created disabled, enabled manually

- **Example Rules**
  - 풀피어싱: rolled_value == max_level on 피어싱 레벨
  - S르그50: erg_grade=="S" AND erg_level==50
  - 붉개7: special_upgrade_type + level>=7
  - Enchant names: prefix/suffix name → tag

---

# 4. In-Game Verification
## OTP via game all-chat. Prove character ownership.

- **Flow**
  - 1. User requests verification → gets code: 마트레-482957
  - 2. User sends code in-game via horn bugle (all-chat)
  - 3. Scheduled job polls Nexon API every 20 min (4 servers)
  - 4. Match: character_name + code → verified = true
  - 5. Verified badge appears next to player name

- **Design Decisions**
  - Non-mandatory — all services work without verification
  - Social proof, not access control
  - 288 API calls/day (well under 1000 limit)
  - Changing server/game_id resets verification
  - 30-min code expiry matches API history window

---

# 5. Self-Correcting OCR
## The system improves from its own usage

- **Feedback Loop**
  - OCR produces text → User sees result in registration form
  - User corrects a line → Both original + corrected saved
  - Line crop image preserved for training
  - Admin reviews & approves corrections
  - Approved corrections feed next model training

- **Quality Signals**
  - confidence — low score = likely OCR error
  - fm_applied — FM overrides that users undo reveal dictionary gaps
  - charset_mismatch — corrected text has chars not in model charset

> More users → more corrections → better training data → more accurate OCR → fewer corrections

---

# Bonus: Automatic Audit Trail

- SQLAlchemy before_flush hook captures all admin CRUD
- Git-diff style before/after JSON for every change
- Zero per-endpoint code — one middleware, all models covered
- Separate table from user activity (recommendations stay clean)
- Source field: 'admin' vs 'system' (jobs)

---

# Thank you
## Mabinogi Marketplace
