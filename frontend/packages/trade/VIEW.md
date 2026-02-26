# Trade Views

## App Layout

```
+--sidebar(w-56)--+------main(flex-1, scroll-y)-------------------+
| [prism] MABI    |                                                |
|                 |  (page content rendered here)                  |
| * Marketplace   |                                                |
| * Sell Item     |                                                |
|                 |                                                |
|                 |                                                |
+-----------------+------------------------------------------------+
```

- **Sidebar**: `src/components/Sidebar.jsx` — fixed left nav, favicon + brand top, active link highlighted
- **Routes**: `/` → Marketplace, `/sell` → Sell

---

## / — Marketplace

```
+--header----------------------------------------------------------+
| [bag] Marketplace               [____Search game items...____]   |
+------------------------------------------------------------------+
|                                     |                            |
|  item-grid (lg:col-span-2)         |  detail-sidebar (col-1)    |
|  +------------------------------+  |  +------------------------+|
|  | [Prefix] Name [Suffix]       |  |  | Item Name              ||
|  | item_type  item_grade        |  |  | game_item_name         ||
|  | reforge ×3  ERG S-25         |  |  | item_type  item_grade  ||
|  +------------------------------+  |  |                        ||
|  +------------------------------+  |  | prefix_enchant:        ||
|  | [Prefix] Name [Suffix]       |  |  |   effect  value        ||
|  | item_type  item_grade        |  |  | suffix_enchant:        ||
|  | reforge ×3  ERG S-25         |  |  |   effect  value        ||
|  +------------------------------+  |  |                        ||
|                                     |  | reforge_options:       ||
|                                     |  |   option  Lv 15/20    ||
|                                     |  +------------------------+|
+-------------------------------------+----------------------------+
```

- **Item cards**: 2-col grid on md+, click selects → detail sidebar populates
  - Shows `prefix_enchant_name` / `suffix_enchant_name` as colored badges
  - Shows `item_type`, `item_grade`, `erg_grade`/`erg_level` inline
  - Reforge count badge
- **Detail sidebar**: sticky, shows selected listing detail
  - Enchant effects: rolled `value` in cyan, fixed (from `min_value`) in gray
  - Reforge options with `level`/`max_level`
- **Game item filter**: typeahead search via API (`GET /game-items?q=...`), filters listings by `game_item_id`
- **Empty state**: dashed box "Select an item to view details"

---

## /sell — Sell Item

```
+--header----------------------------------------------------------+
| SELL ITEM                                       [Scan Successful]|
| Register your Mabinogi items via OCR                             |
+------------------------------------------------------------------+
|                               |                                  |
|  left-col (xl:4)              |  right-col (xl:8)                |
|  +--Upload Tooltip-[SCAN]---+|  +--ITEM DETAILS----------------+|
|  |                           ||  | orange accent bar            ||
|  |  [drop zone / preview]    ||  | ITEM DETAILS       V1.0     ||
|  |                           ||  |                              ||
|  +---------------------------+|  | Game Item [search] Name_ Price|
|                               |  |                              ||
|  +--OCR METRICS--------------+|  | Detected Categories:         ||
|  | Total Lines | Sections    ||  | > Attributes  [v]            ||
|  | 24          | 6           ||  |   [line input_________]      ||
|  +---------------------------+|  |   [line input_________]      ||
|                               |  | > Enchant  [v]               ||
|                               |  |   prefix: name  Rank A       ||
|                               |  |     - effect  [level]        ||
|                               |  |   suffix: name  Rank 9       ||
|                               |  |     - effect  [level]        ||
|                               |  | > Reforge  [v]               ||
|                               |  |   option  Level 3/20         ||
|                               |  | > Item Color  [v]            ||
|                               |  |   [R,G,B] [R,G,B] [R,G,B]   ||
|                               |  |                              ||
|                               |  | [====Register Item====] [R]  ||
|                               |  +------------------------------+|
+-------------------------------+----------------------------------+
```

- **Left column**: image upload with drag-drop zone, OCR metrics card
  - **Scan button** is in the header row of "Upload Tooltip" card (always visible regardless of image height)
  - Loading spinner replaces scan button during processing
- **Right column**: structured form populated by OCR
  - **Top row** (3 fields):
    - Game Item selector: typeahead search against `window.GAME_ITEMS_CONFIG` (local, no API call). Sets `game_item_id` FK. Auto-populated from OCR item name.
    - Listing Name: user-editable display name (independent of game item). Auto-populated from OCR.
    - Price: numeric input with comma formatting.
  - `SectionCard` per detected category (collapsible)
  - `EnchantSection`: prefix/suffix slots with editable effects via `ConfigSearchInput`
  - `ReforgeSection`: options with editable name/level, `reforge_option_id` resolved from `window.REFORGES_CONFIG`
  - `ColorPartsSection`: 3-col RGB swatch grid
  - `DefaultSection`: generic text inputs with low-confidence warning
- **Register**: submits to `POST /register-listing` with:
  - `session_id`, `name`, `price`, `game_item_id`
  - `item_type`, `item_grade`, `erg_grade`, `erg_level` (from OCR sections)
  - `enchants[]` (structured prefix/suffix with effects)
  - `reforge_options[]` (with `reforge_option_id` from static config)
  - `lines[]` (for OCR correction capture)
