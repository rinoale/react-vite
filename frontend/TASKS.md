# Frontend Tasks: Attempt 17 (V3 Pipeline)

Implementation of a structured, category-aware UI for Mabinogi item registration.

## 1. Image Upload & Preprocessing
- [x] **Switch to Color Uploads:** Update `src/pages/sell.jsx` to send original color images (or high-quality JPEGs) instead of binarized White-on-Black crops.
- [x] **Multi-Step Progress State:** Add a status indicator for backend processing:
  - `SEGMENTING`: "Detecting item sections (Attributes, Enchants, etc.)..."
  - `RECOGNIZING`: "Reading text stats..."
  - `POST_PROCESSING`: "Applying fuzzy corrections..."
- [ ] **Error Handling:** Add UI for segmentation failure (e.g., "Could not find orange headers. Please ensure the tooltip is clearly visible.")

## 2. Structured Item Registration Form
- [x] **Header Section:**
  - Item Name (Editable text)
  - Grade (Select dropdown: None, Normal, Rare, Master, Epic, etc.)
- [x] **Dynamic Category Cards:** Create components for the 7 primary "Fieldset" boxes (only show if detected):
  - **Attributes** (아이템 속성): Multi-line stat editor.
  - **Enchant** (인챈트): Separate fields for [Prefix] and [Suffix].
  - **Upgrade** (개조): Mod count (N/N) and Gem upgrade status.
  - **Reforge** (세공): List of options with Level (N/20).
  - **Erg** (에르그): Level and current effect.
  - **Set Item** (세트아이템): List of active set effects.
  - **Item Color** (아이템 색상): RGB color boxes for Part A-F.

## 2.1 Reforge Details (Refinement)
- [x] **Reforge Row:** Map `reforge_name`, `reforge_level`, and `reforge_max_level` to structured inputs.

## 3. Data Integration (API)
- [x] **Update Endpoint:** Point to `/upload-item-v3` (or the V3-compatible endpoint in `backend/main.py`).
- [x] **JSON Mapping:** map the structured response (e.g., `item_attrs`, `enchant`, `reforge` objects) to React `useState` state.
- [ ] **Segment Previews:** If backend returns base64 crops of sections, display them next to the corresponding input fields for easy verification.

## 4. UX & Validation
- [x] **Confidence Highlighting:** Highlight characters or lines with low OCR confidence (e.g., `< 0.7`) using a subtle red underline or background.
- [ ] **Fuzzy Search Pickers:** Integrate an autocomplete/dropdown for Enchant names and Reforge options using the `data/dictionary/` content (can be fetched or pre-loaded).
- [x] **Mabinogi Themeing:** Apply "Mabinogi-like" CSS (thin gray borders, orange legend text) to the category cards.

## 6. Admin Dashboard
- [x] **Enchant List with Effects:** Create `/admin` page that lists all enchant entries.
- [x] **Expandable Detail:** Clicking an enchant entry expands to show its associated effects, conditions, and metadata.
- [ ] **Dynamic Link Filtering:** Update UI to fetch effects on-demand once the backend supports `?enchant_entry_id=N` filter. (Currently relies on 500-link cache).
- [ ] **Reforge Validation:** Add a tab or view for validating all reforge options.
