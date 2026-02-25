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
| [bag] Marketplace                   [____Search for items...___] |
+------------------------------------------------------------------+
|                                     |                            |
|  item-grid (lg:col-span-2)         |  detail-sidebar (col-1)    |
|  +----------+  +----------+        |  +------------------------+|
|  | name  cat|  | name  cat|        |  | Item Name              ||
|  | desc...  |  | desc...  |        |  | [category]             ||
|  +----------+  +----------+        |  | description...         ||
|  +----------+  +----------+        |  |                        ||
|  | name  cat|  | name  cat|        |  | [====Buy Now====]      ||
|  | desc...  |  | desc...  |        |  |________________________||
|  +----------+  +----------+        |  | * Recommended for You  ||
|                                     |  | rec-item  87% match    ||
|                                     |  | rec-item  74% match    ||
|                                     |  +------------------------+|
+-------------------------------------+----------------------------+
```

- **Item cards**: 2-col grid on md+, click selects → detail sidebar populates
- **Detail sidebar**: sticky, shows selected item + TF-IDF recommendations
- **Empty state**: dashed box "Select an item to view details and recommendations"

---

## /sell — Sell Item

```
+--header----------------------------------------------------------+
| SELL ITEM                                       [Scan Successful]|
| Register your Mabinogi items via OCR                             |
+------------------------------------------------------------------+
|                               |                                  |
|  left-col (xl:4)              |  right-col (xl:8)                |
|  +--Upload Tooltip----------+|  +--ITEM DETAILS----------------+|
|  |                           ||  | orange accent bar            ||
|  |  [drop zone / preview]    ||  | ITEM DETAILS       V1.0     ||
|  |                           ||  |                              ||
|  |  [====Scan Tooltip====]   ||  | Item Name______  Price______ ||
|  +---------------------------+|  |                              ||
|                               |  | Detected Categories:         ||
|  +--OCR METRICS--------------+|  | > Attributes  [v]            ||
|  | Total Lines | Sections    ||  |   [line input_________]      ||
|  | 24          | 6           ||  |   [line input_________]      ||
|  +---------------------------+|  | > Enchant  [v]               ||
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

- **Left column**: image upload with drag-drop zone, scan button, OCR metrics card
- **Right column**: structured form populated by OCR
  - `SectionCard` per detected category (collapsible)
  - `EnchantSection`: prefix/suffix slots with editable effects via `ConfigSearchInput`
  - `ReforgeSection`: options with editable name/level
  - `ColorPartsSection`: 3-col RGB swatch grid
  - `DefaultSection`: generic text inputs with low-confidence warning
- **Register**: submits session_id + edited lines to `/register-item`
