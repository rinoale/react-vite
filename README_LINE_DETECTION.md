# Automated Text Line Detection for Mabinogi Item Tooltips

I've added automated line detection to both browser and Python solutions to eliminate manual labor!

## 🌐 Browser Solution (Updated image_process.jsx)

### New Features Added:
1. **"Detect Text Lines" button** - Automatically splits image into text lines
2. **Auto-detected segments section** - Shows detected lines with text inputs
3. **"Add All Auto-Detected Lines" button** - Add all to dataset at once

### How It Works:
- Uses **horizontal projection analysis** to detect text lines
- Calculates density of black pixels in each row
- Finds peaks indicating text lines
- Automatically extracts line regions

## 🐍 Python Solution (tooltip_line_splitter.py)

### Advanced Computer Vision Approach:
```bash
# Install dependencies first
pip install opencv-python numpy Pillow

# Process single image
python3 tooltip_line_splitter.py item_tooltip.png

# Process directory of images
python3 tooltip_line_splitter.py /path/to/tooltips/ -o output_dir

# With custom settings
python3 tooltip_line_splitter.py item.png --min-height 10 --max-height 40
```

### Python Features:
- **Connected Component Analysis** - Finds individual text regions
- **Adaptive Thresholding** - Better text extraction from tooltips
- **Morphological Operations** - Cleans up noise
- **Line Merging** - Combines broken text fragments
- **Visualization** - Shows detected lines with bounding boxes
- **Batch Processing** - Process hundreds of images at once

### Output Structure:
```
split_output/
├── images/
│   ├── item_line_001.png
│   ├── item_line_002.png
│   └── ...
├── item_manifest.json
├── item_visualization.png
└── processing_summary.json
```

## 📊 Comparison:

| Method | Pros | Cons |
|--------|------|------|
| **Browser JS** | No installation, instant, interactive | Limited accuracy, basic algorithm |
| **Python CV2** | High accuracy, batch processing, advanced features | Requires dependencies |

## 🎯 Usage Recommendation:

1. **For quick testing**: Use browser version
2. **For production**: Use Python script
3. **Best workflow**: Process with Python → Fine-tune with browser tool

## 🔧 Installation:

```bash
# For Python solution
pip install opencv-python numpy Pillow

# Make executable
chmod +x tooltip_line_splitter.py
```

The Python solution can process hundreds of tooltip images automatically and achieve much better accuracy than manual selection!