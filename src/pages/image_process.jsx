import React, { useState, useRef, useEffect } from 'react';
import { Upload, Download, Settings, FileText, Scissors, X } from 'lucide-react';

const MabinogiTesseractPrep = () => {
  const [image, setImage] = useState(null);
  const [processedImage, setProcessedImage] = useState(null);
  const [settings, setSettings] = useState({
    contrast: 1.5,
    brightness: 1.2,
    threshold: 128,
    useAdaptive: false,
    colorChannel: 'grayscale'
  });
  const [images, setImages] = useState([]);
  const [lineSegments, setLineSegments] = useState([]);
  const [showSegmentation, setShowSegmentation] = useState(false);
  
  // Manual selection states
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const [currentSelection, setCurrentSelection] = useState(null);
  const [manualSegments, setManualSegments] = useState([]);
  
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);
  const displayCanvasRef = useRef(null);

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
          setImage(img);
          processImage(img);
          setManualSegments([]);
        };
        img.src = event.target.result;
      };
      reader.readAsDataURL(file);
    }
  };

  const processImage = (img) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    canvas.width = img.width;
    canvas.height = img.height;
    
    ctx.drawImage(img, 0, 0);
    let imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;

    if (settings.colorChannel === 'grayscale') {
      for (let i = 0; i < data.length; i += 4) {
        const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        data[i] = data[i + 1] = data[i + 2] = gray;
      }
    } else if (settings.colorChannel === 'red') {
      for (let i = 0; i < data.length; i += 4) {
        data[i + 1] = data[i + 2] = 0;
      }
    } else if (settings.colorChannel === 'green') {
      for (let i = 0; i < data.length; i += 4) {
        data[i] = data[i + 2] = 0;
      }
    } else if (settings.colorChannel === 'blue') {
      for (let i = 0; i < data.length; i += 4) {
        data[i] = data[i + 1] = 0;
      }
    }

    for (let i = 0; i < data.length; i += 4) {
      data[i] = Math.min(255, Math.max(0, settings.contrast * (data[i] - 128) + 128 + (settings.brightness - 1) * 128));
      data[i + 1] = Math.min(255, Math.max(0, settings.contrast * (data[i + 1] - 128) + 128 + (settings.brightness - 1) * 128));
      data[i + 2] = Math.min(255, Math.max(0, settings.contrast * (data[i + 2] - 128) + 128 + (settings.brightness - 1) * 128));
    }

    if (settings.useAdaptive) {
      applyAdaptiveThreshold(data, canvas.width, canvas.height);
    } else {
      for (let i = 0; i < data.length; i += 4) {
        const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
        const val = avg > settings.threshold ? 255 : 0;
        data[i] = data[i + 1] = data[i + 2] = val;
      }
    }

    ctx.putImageData(imageData, 0, 0);
    setProcessedImage(canvas.toDataURL());
  };

  const applyAdaptiveThreshold = (data, width, height, blockSize = 15) => {
    const temp = new Uint8ClampedArray(data.length);
    for (let i = 0; i < data.length; i++) temp[i] = data[i];

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        let sum = 0, count = 0;
        const halfBlock = Math.floor(blockSize / 2);
        
        for (let by = Math.max(0, y - halfBlock); by <= Math.min(height - 1, y + halfBlock); by++) {
          for (let bx = Math.max(0, x - halfBlock); bx <= Math.min(width - 1, x + halfBlock); bx++) {
            const idx = (by * width + bx) * 4;
            sum += temp[idx];
            count++;
          }
        }
        
        const threshold = sum / count - 10;
        const idx = (y * width + x) * 4;
        const val = temp[idx] > threshold ? 255 : 0;
        data[idx] = data[idx + 1] = data[idx + 2] = val;
      }
    }
  };

  const handleSettingChange = (key, value) => {
    const newSettings = { ...settings, [key]: value };
    setSettings(newSettings);
    if (image) {
      processImage(image);
    }
  };

  // Manual selection handlers
  const handleMouseDown = (e) => {
    if (!displayCanvasRef.current) return;
    const canvas = displayCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // Account for canvas scaling
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    
    setIsSelecting(true);
    setSelectionStart({ x, y });
    setSelectionEnd({ x, y });
  };

  const handleMouseMove = (e) => {
    if (!isSelecting || !displayCanvasRef.current) return;
    const canvas = displayCanvasRef.current;
    const rect = canvas.getBoundingClientRect();
    
    // Account for canvas scaling
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    
    setSelectionEnd({ x, y });
  };

  const handleMouseUp = () => {
    if (!isSelecting || !selectionStart || !selectionEnd) return;
    
    const x = Math.min(selectionStart.x, selectionEnd.x);
    const y = Math.min(selectionStart.y, selectionEnd.y);
    const width = Math.abs(selectionEnd.x - selectionStart.x);
    const height = Math.abs(selectionEnd.y - selectionStart.y);
    
    if (width > 5 && height > 5) {
      setCurrentSelection({ x, y, width, height });
    }
    
    setIsSelecting(false);
  };

  const addSelection = () => {
    if (!currentSelection || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const segmentCanvas = document.createElement('canvas');
    const ctx = segmentCanvas.getContext('2d');
    
    // currentSelection is already in canvas coordinates, no scaling needed
    const x = currentSelection.x;
    const y = currentSelection.y;
    const width = currentSelection.width;
    const height = currentSelection.height;
    
    segmentCanvas.width = width;
    segmentCanvas.height = height;
    
    ctx.drawImage(canvas, x, y, width, height, 0, 0, width, height);
    
    const newSegment = {
      id: Date.now(),
      image: segmentCanvas.toDataURL(),
      text: '',
      filename: `segment_${manualSegments.length + 1}.png`,
      bounds: currentSelection
    };
    
    setManualSegments([...manualSegments, newSegment]);
    setCurrentSelection(null);
    setSelectionStart(null);
    setSelectionEnd(null);
  };

  const removeSegment = (id) => {
    setManualSegments(manualSegments.filter(seg => seg.id !== id));
  };

  const updateSegmentText = (id, text) => {
    setManualSegments(prev => 
      prev.map(seg => seg.id === id ? { ...seg, text } : seg)
    );
  };

  const addSegmentsToDataset = () => {
    const validSegments = manualSegments.filter(seg => seg.text.trim());
    setImages(prev => [...prev, ...validSegments]);
    setManualSegments([]);
    setCurrentSelection(null);
  };

  const downloadDataset = () => {
    images.forEach((item) => {
      const link = document.createElement('a');
      link.href = item.image;
      link.download = item.filename;
      link.click();

      const textBlob = new Blob([item.text], { type: 'text/plain' });
      const textUrl = URL.createObjectURL(textBlob);
      const textLink = document.createElement('a');
      textLink.href = textUrl;
      textLink.download = item.filename.replace('.png', '.gt.txt');
      textLink.click();
      URL.revokeObjectURL(textUrl);
    });
  };

  const downloadTrainingScript = () => {
    const script = `#!/bin/bash
# Tesseract Training Script for Mabinogi Item Tooltips

# 1. Combine images into a TIFF file
for img in *.png; do
    convert "$img" "\${img%.png}.tif"
done

# 2. Generate box files (manual correction needed)
for img in *.tif; do
    tesseract "$img" "\${img%.tif}" -l kor box.train
done

echo "Box files generated. Please manually correct them before proceeding."
`;

    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'train_tesseract.sh';
    link.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (!processedImage || !displayCanvasRef.current) return;
    
    const canvas = displayCanvasRef.current;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      
      // Draw existing segments
      manualSegments.forEach(seg => {
        ctx.strokeStyle = '#22d3ee';
        ctx.lineWidth = 2;
        ctx.strokeRect(seg.bounds.x, seg.bounds.y, seg.bounds.width, seg.bounds.height);
      });
      
      // Draw current selection
      if (currentSelection) {
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.strokeRect(currentSelection.x, currentSelection.y, currentSelection.width, currentSelection.height);
      }
      
      // Draw active selection
      if (isSelecting && selectionStart && selectionEnd) {
        const x = Math.min(selectionStart.x, selectionEnd.x);
        const y = Math.min(selectionStart.y, selectionEnd.y);
        const width = Math.abs(selectionEnd.x - selectionStart.x);
        const height = Math.abs(selectionEnd.y - selectionStart.y);
        
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(x, y, width, height);
        ctx.setLineDash([]);
      }
    };
    
    img.src = processedImage;
  }, [processedImage, manualSegments, currentSelection, isSelecting, selectionStart, selectionEnd]);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2 text-cyan-400">Mabinogi Tesseract Training Prep</h1>
        <p className="text-gray-400 mb-6">Preprocess item tooltip images and prepare training data</p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Image Processing</h2>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageUpload}
              accept="image/*"
              className="hidden"
            />
            
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full bg-cyan-600 hover:bg-cyan-700 text-white py-3 rounded-lg mb-4 flex items-center justify-center gap-2"
            >
              <Upload className="w-5 h-5" />
              Upload Item Tooltip Image
            </button>

            {image && (
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-medium mb-2">Original Image</h3>
                  <img src={image.src} alt="Original" className="w-full border border-gray-700 rounded" />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-sm font-medium">Processed Image</h3>
                    <span className="text-xs text-gray-400">Drag to select text regions</span>
                  </div>
                  {processedImage && (
                    <div className="relative">
                      <canvas
                        ref={displayCanvasRef}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        className="w-full border border-gray-700 rounded cursor-crosshair"
                      />
                      {currentSelection && (
                        <button
                          onClick={addSelection}
                          className="mt-2 w-full bg-green-600 hover:bg-green-700 text-white py-2 rounded-lg flex items-center justify-center gap-2"
                        >
                          <Scissors className="w-4 h-4" />
                          Add Selected Region
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <canvas ref={canvasRef} className="hidden" />
          </div>

          <div className="space-y-6">
            <div className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Settings className="w-5 h-5" />
                Processing Settings
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Contrast: {settings.contrast.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="3"
                    step="0.1"
                    value={settings.contrast}
                    onChange={(e) => handleSettingChange('contrast', parseFloat(e.target.value))}
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    Brightness: {settings.brightness.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.1"
                    value={settings.brightness}
                    onChange={(e) => handleSettingChange('brightness', parseFloat(e.target.value))}
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    Threshold: {settings.threshold}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="255"
                    step="1"
                    value={settings.threshold}
                    onChange={(e) => handleSettingChange('threshold', parseInt(e.target.value))}
                    className="w-full"
                    disabled={settings.useAdaptive}
                  />
                </div>

                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={settings.useAdaptive}
                      onChange={(e) => handleSettingChange('useAdaptive', e.target.checked)}
                      className="w-4 h-4"
                    />
                    <span className="text-sm">Use Adaptive Threshold</span>
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Color Channel</label>
                  <select
                    value={settings.colorChannel}
                    onChange={(e) => handleSettingChange('colorChannel', e.target.value)}
                    className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
                  >
                    <option value="grayscale">Grayscale</option>
                    <option value="red">Red Channel</option>
                    <option value="green">Green Channel</option>
                    <option value="blue">Blue Channel</option>
                    <option value="original">Original</option>
                  </select>
                </div>
              </div>
            </div>

            {manualSegments.length > 0 && (
              <div className="bg-gray-800 rounded-lg p-6">
                <h2 className="text-xl font-semibold mb-4">Selected Segments ({manualSegments.length})</h2>
                
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {manualSegments.map((segment) => (
                    <div key={segment.id} className="border border-gray-700 rounded p-3">
                      <div className="flex gap-3 mb-2">
                        <img src={segment.image} alt={segment.filename} className="h-16 border border-gray-600" />
                        <button
                          onClick={() => removeSegment(segment.id)}
                          className="ml-auto text-red-400 hover:text-red-300"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                      <textarea
                        value={segment.text}
                        onChange={(e) => updateSegmentText(segment.id, e.target.value)}
                        placeholder="Enter text for this segment..."
                        className="w-full h-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm resize-none"
                      />
                    </div>
                  ))}
                </div>

                <button
                  onClick={addSegmentsToDataset}
                  className="w-full mt-4 bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg"
                >
                  Add All Segments to Dataset
                </button>
              </div>
            )}
          </div>
        </div>

        {images.length > 0 && (
          <div className="mt-6 bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Training Dataset ({images.length} images)</h2>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              {images.map((item) => (
                <div key={item.id} className="border border-gray-700 rounded p-2">
                  <img src={item.image} alt={item.filename} className="w-full mb-2" />
                  <p className="text-xs text-gray-400 truncate">{item.filename}</p>
                </div>
              ))}
            </div>

            <div className="flex gap-4">
              <button
                onClick={downloadDataset}
                className="flex-1 bg-cyan-600 hover:bg-cyan-700 text-white py-3 rounded-lg flex items-center justify-center gap-2"
              >
                <Download className="w-5 h-5" />
                Download All Images & Text Files
              </button>
              
              <button
                onClick={downloadTrainingScript}
                className="flex-1 bg-purple-600 hover:bg-purple-700 text-white py-3 rounded-lg flex items-center justify-center gap-2"
              >
                <Download className="w-5 h-5" />
                Download Training Script
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Quick Guide</h2>
          <ol className="space-y-2 text-sm text-gray-300">
            <li><strong>1.</strong> Upload an item tooltip image from Mabinogi</li>
            <li><strong>2.</strong> Adjust processing settings to get clear text</li>
            <li><strong>3.</strong> <strong className="text-cyan-400">Drag with your mouse to select text regions</strong></li>
            <li><strong>4.</strong> Click "Add Selected Region" for each selection</li>
            <li><strong>5.</strong> Type the text for each segment</li>
            <li><strong>6.</strong> Click "Add All Segments to Dataset"</li>
            <li><strong>7.</strong> Repeat for many tooltips, then download everything!</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

export default MabinogiTesseractPrep;
