import React, { useState, useRef, useEffect } from 'react';
import { Upload, Loader2, Save, X, Settings, RotateCw } from 'lucide-react';

const Sell = () => {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [processedUrl, setProcessedUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [detectedLines, setDetectedLines] = useState([]);
  const [showSettings, setShowSettings] = useState(false);
  
  // Image Processing Settings
  const [settings, setSettings] = useState({
    contrast: 3.0,
    brightness: 2.0,
    threshold: 120,
    useAdaptive: false,
    colorChannel: 'grayscale'
  });

  const canvasRef = useRef(null);

  // Form Data
  const [formData, setFormData] = useState({
    name: '',
    price: '',
    category: 'weapon', // default
    description: '',
    stats: [] 
  });

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setDetectedLines([]);
      setFormData(prev => ({ ...prev, description: '' }));
    }
  };

  // Process Image Effect - Runs when file or settings change
  useEffect(() => {
    if (file) {
      processImageOnCanvas(file);
    }
  }, [file, settings]);

  const processImageOnCanvas = (fileObject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        
        canvas.width = img.width;
        canvas.height = img.height;
        
        ctx.drawImage(img, 0, 0);
        let imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;

        // 1. Grayscale Conversion (Standard weighted)
        for (let i = 0; i < data.length; i += 4) {
            const gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
            data[i] = data[i + 1] = data[i + 2] = gray;
        }

        // 2. Contrast & Brightness
        for (let i = 0; i < data.length; i += 4) {
            data[i] = Math.min(255, Math.max(0, settings.contrast * (data[i] - 128) + 128 + (settings.brightness - 1) * 128));
            data[i + 1] = Math.min(255, Math.max(0, settings.contrast * (data[i + 1] - 128) + 128 + (settings.brightness - 1) * 128));
            data[i + 2] = Math.min(255, Math.max(0, settings.contrast * (data[i + 2] - 128) + 128 + (settings.brightness - 1) * 128));
        }

        // 3. Thresholding (Simple or Adaptive)
        for (let i = 0; i < data.length; i += 4) {
            const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
            // Thresholding: Text is Light, Background is Dark.
            // We want White Text (255) on Black Background (0) to match training data.
            // If pixel is BRIGHT (> threshold), it's TEXT -> Make it WHITE (255).
            // Else (Background), set to BLACK (0).
            
            const val = avg > settings.threshold ? 255 : 0;
            
            data[i] = data[i + 1] = data[i + 2] = val;
        }

        ctx.putImageData(imageData, 0, 0);
        setProcessedUrl(canvas.toDataURL('image/png'));
      };
      img.src = event.target.result;
    };
    reader.readAsDataURL(fileObject);
  };

  const handleScan = async () => {
    if (!processedUrl) return;

    setIsLoading(true);
    
    // Convert DataURL to Blob
    const response = await fetch(processedUrl);
    const blob = await response.blob();
    const processedFile = new File([blob], "processed_item.png", { type: "image/png" });

    const formDataUpload = new FormData();
    formDataUpload.append('file', processedFile);

    try {
      const res = await fetch('http://localhost:8000/upload-item', {
        method: 'POST',
        body: formDataUpload,
      });

      if (!res.ok) throw new Error('Failed to process image');

      const data = await res.json();
      setDetectedLines(data.detected_lines);
      
      if (data.detected_lines.length > 0) {
        // Use the raw_text_summary or build from corrected lines
        // Ideally, we want the corrected text.
        // My backend returns "text" (corrected) and "raw_text".
        
        const fullText = data.detected_lines.map(l => l.text).join('\n');
        // Guess name (usually first line)
        const guessedName = data.detected_lines[0].text;
        
        setFormData(prev => ({
          ...prev,
          name: guessedName,
          description: fullText
        }));
      }

    } catch (error) {
      console.error("Error processing image:", error);
      alert("Error scanning image. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-8 text-cyan-400">List New Item</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Column: Image Upload & Preview */}
          <div className="space-y-6">
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">Item Image</h2>
                <button 
                  onClick={() => setShowSettings(!showSettings)}
                  className="text-gray-400 hover:text-white p-2 rounded-full hover:bg-gray-700"
                  title="Advanced Processing Settings"
                >
                  <Settings className="w-5 h-5" />
                </button>
              </div>
              
              {!previewUrl ? (
                <div className="border-2 border-dashed border-gray-600 rounded-lg h-64 flex flex-col items-center justify-center text-gray-400 hover:border-cyan-500 hover:text-cyan-500 transition-colors cursor-pointer relative">
                  <input 
                    type="file" 
                    onChange={handleFileChange} 
                    accept="image/*"
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  <Upload className="w-12 h-12 mb-2" />
                  <span>Click to upload screenshot</span>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="relative">
                    {/* Show Original Image for better UX, but upload processed */}
                    <img 
                      src={previewUrl} 
                      alt="Item Preview" 
                      className="w-full rounded-lg shadow-lg border border-gray-700"
                    />
                    <button 
                      onClick={() => {
                          setFile(null);
                          setPreviewUrl(null);
                          setProcessedUrl(null);
                          setDetectedLines([]);
                      }}
                      className="absolute top-2 right-2 bg-red-600 p-1 rounded-full hover:bg-red-700 text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  
                  {/* Settings Panel */}
                  {showSettings && (
                    <div className="bg-gray-700/50 p-4 rounded-lg text-sm space-y-3">
                        <div>
                            <label className="flex justify-between mb-1">
                                <span>Contrast</span>
                                <span>{settings.contrast}</span>
                            </label>
                            <input 
                                type="range" min="0.5" max="5" step="0.1" 
                                value={settings.contrast}
                                onChange={(e) => setSettings({...settings, contrast: parseFloat(e.target.value)})}
                                className="w-full"
                            />
                        </div>
                        <div>
                            <label className="flex justify-between mb-1">
                                <span>Brightness</span>
                                <span>{settings.brightness}</span>
                            </label>
                            <input 
                                type="range" min="0.5" max="3" step="0.1" 
                                value={settings.brightness}
                                onChange={(e) => setSettings({...settings, brightness: parseFloat(e.target.value)})}
                                className="w-full"
                            />
                        </div>
                        <div>
                            <label className="flex justify-between mb-1">
                                <span>Threshold</span>
                                <span>{settings.threshold}</span>
                            </label>
                            <input 
                                type="range" min="0" max="255" step="1" 
                                value={settings.threshold}
                                onChange={(e) => setSettings({...settings, threshold: parseInt(e.target.value)})}
                                className="w-full"
                            />
                        </div>
                    </div>
                  )}
                </div>
              )}

              {file && !isLoading && (
                <button
                  onClick={handleScan}
                  className="w-full mt-4 bg-cyan-600 hover:bg-cyan-700 text-white py-3 rounded-lg flex items-center justify-center gap-2 font-medium transition-colors"
                >
                  <Upload className="w-5 h-5" />
                  Scan Processed Image
                </button>
              )}

              {isLoading && (
                <div className="w-full mt-4 bg-gray-700 text-gray-300 py-3 rounded-lg flex items-center justify-center gap-2 cursor-wait">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Processing...
                </div>
              )}
            </div>

            {/* Debug View for Detected Lines */}
            {detectedLines.length > 0 && (
              <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Detected Lines (Corrected)</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                  {detectedLines.map((line, idx) => (
                    <div key={idx} className="bg-gray-700/50 p-2 rounded text-sm text-gray-300 flex flex-col gap-1">
                      <div className="flex justify-between">
                        <span className="text-cyan-400 font-medium">{line.text}</span>
                        <span className="text-xs text-gray-500">{Math.round(line.confidence * 100)}%</span>
                      </div>
                      {line.text !== line.raw_text && (
                         <span className="text-xs text-gray-500 line-through">{line.raw_text}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Item Details Form */}
          <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
            <h2 className="text-xl font-semibold mb-6">Item Details</h2>
            
            <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Item Name</label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  placeholder="e.g. Dragon Blade"
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Price (Gold)</label>
                  <input
                    type="number"
                    name="price"
                    value={formData.price}
                    onChange={handleInputChange}
                    placeholder="0"
                    className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Category</label>
                  <select
                    name="category"
                    value={formData.category}
                    onChange={handleInputChange}
                    className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none"
                  >
                    <option value="weapon">Weapon</option>
                    <option value="armor">Armor</option>
                    <option value="accessory">Accessory</option>
                    <option value="consumable">Consumable</option>
                    <option value="material">Material</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Description / Stats</label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  rows={15}
                  placeholder="Item stats and description..."
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none resize-none font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  * Automatically populated from image scan. Please verify accuracy.
                </p>
              </div>

              <div className="pt-4 border-t border-gray-700">
                <button
                  type="submit"
                  className="w-full bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg flex items-center justify-center gap-2 font-bold text-lg transition-transform active:scale-95"
                >
                  <Save className="w-5 h-5" />
                  List Item for Sale
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      
      {/* Hidden Canvas for Processing */}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
};

export default Sell;