# Project Context: Online Game Item Trade Website

## 1. Main Purpose
Build a specialized marketplace for trading in-game items where the core data entry is automated via image recognition (OCR).

## 2. Key Features

### A. OCR-based Item Registration
- **User Action:** Uploads a screenshot of the game item.
- **System Action:** 
  - Parses the image to detect text lines (using `tooltip_line_splitter.py` logic).
  - Extracts text content (Item Name, Stats, Options) using OCR (EasyOCR).
  - Populates the "Sell Item" form with this data for user verification.
- **Goal:** Minimize manual typing and ensure accurate stat-based searching.

### B. Advanced Search & Database
- **Storage:** Structured storage of item stats (e.g., "Fire Damage", "Durability", "Rarity") rather than just plain text descriptions.
- **Search:** Users can filter by specific attributes (e.g., "Find Sword with > 100 Attack").

### C. Recommendation Algorithm
- **Logic:** Implement a "YouTube-like" recommendation system.
- **Inputs:**
  - User's recent search queries.
  - User's transaction history (bought/sold items).
  - Item similarity (content-based filtering).
- **Output:** "Recommended for you" section on the home page and item detail page.

## 3. Technology Stack
- **Frontend:** React + Vite + Tailwind CSS.
- **Backend:** Python (FastAPI) to handle OCR processing and recommendation logic.
- **Database:** SQLite/PostgreSQL to store item properties and user history.

## 4. General Guidelines
- Ask before making changes.
- Maintain existing code styles (React/Tailwind/Python).