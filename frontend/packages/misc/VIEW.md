# Misc Views

## App Layout

```
+--top-nav(centered)-----------------------------------------------+
| Navigate | Image Process (Debug)                                 |
+------------------------------------------------------------------+
|                                                                  |
|  (page content rendered here)                                    |
|                                                                  |
+------------------------------------------------------------------+
```

- **Routes**: `/navigate` → Navigate, `/image_process` → ImageProcess

---

## /navigate — South Korea Navigation Map

```
+--header(blue-600)------------------------------------------------+
| South Korea Navigation Map                                       |
| Interactive map with address search and location services        |
|                                                                  |
| [____Search address...____] [Search]                             |
| [Get My Location] [Zoom to My Location]                          |
+------------------------------------------------------------------+
|                                                                  |
|  +--leaflet-map(flex-1)----------------------------------------+|
|  |                                                              ||
|  |  [Location Active]     city markers:                         ||
|  |   (floating badge)      Seoul, Busan, Incheon, Daegu,       ||
|  |                          Daejeon, Gwangju, Ulsan, Jeju       ||
|  |                                                              ||
|  |              [user-dot]  (blue circle if geolocated)         ||
|  |              [search-pin] (red pin for search result)        ||
|  |                                                              ||
|  +--------------------------------------------------------------+|
|  [Enable Location Services]  (floating tooltip, bottom-left)     |
+------------------------------------------------------------------+
```

- **Leaflet**: loaded dynamically via CDN script injection
- **Search**: Nominatim geocoding API, limited to South Korea (`countrycodes=kr`)
- **Geolocation**: auto-requested on mount, manual button fallback
- **Full height**: map fills remaining viewport below header

---

## /image_process — Tesseract Training Prep

```
+--header----------------------------------------------------------+
| Mabinogi Tesseract Training Prep                                 |
| Preprocess item tooltip images and prepare training data         |
+------------------------------------------------------------------+
|                               |                                  |
|  left-col (lg:1)              |  right-col (lg:1)                |
|  +--Image Processing--------+|  +--Processing Settings---------+|
|  |                           ||  | Contrast:  [====3.0====]     ||
|  | [Upload Item Tooltip]     ||  | Brightness:[====2.0====]     ||
|  |                           ||  | Threshold: [====120====]     ||
|  | Original Image:           ||  | [x] Adaptive Threshold       ||
|  | [uploaded img]            ||  | Channel: [Grayscale v]       ||
|  |                           ||  +------------------------------+|
|  | Processed Image:          ||                                  |
|  | +------------------------+||  +--Selected Segments (N)-------+|
|  | | [canvas: crosshair]    |||  | [crop-img]          [x]     ||
|  | | (drag to select)       |||  | [text input________]        ||
|  | |  [cyan: existing segs] |||  | [crop-img]          [x]     ||
|  | |  [green: confirmed]    |||  | [text input________]        ||
|  | |  [yellow: active drag] |||  |                              ||
|  | +------------------------+||  | [Add All Segments to Dataset]||
|  | [Add Selected Region]     ||  +------------------------------+|
|  +---------------------------+|                                  |
+-------------------------------+----------------------------------+
|                                                                  |
|  +--Training Dataset (N images)----------------------------------+|
|  | [img] [img] [img] [img]                                      ||
|  | [====Download All====] [====Download Training Script====]     ||
|  +---------------------------------------------------------------+|
|                                                                  |
|  +--Quick Guide--------------------------------------------------+|
|  | 1. Upload  2. Adjust  3. Drag  4. Add  5. Label  6. Export    ||
|  +---------------------------------------------------------------+|
+------------------------------------------------------------------+
```

- **Canvas interaction**: mousedown/move/up for rectangular selection
- **Selection colors**: yellow=dragging, green=confirmed, cyan=saved segments
- **Segments panel**: each segment has crop preview + text input for GT label
- **Dataset**: accumulated image/text pairs, bulk download as individual files
- **Processing**: BT.601 grayscale, contrast/brightness, threshold (fixed or adaptive)
