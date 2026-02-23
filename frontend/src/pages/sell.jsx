import React, { useState, useRef, useEffect } from 'react';
import { Upload, Loader2, Save, X, Settings, RotateCw, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight } from 'lucide-react';

const CATEGORY_LABELS = {
  item_name: "Item Name",
  item_type: "Item Type",
  item_grade: "Grade",
  item_attrs: "Attributes (아이템 속성)",
  enchant: "Enchant (인챈트)",
  item_mod: "Upgrade (개조)",
  reforge: "Reforge (세공)",
  erg: "Erg (에르그)",
  set_item: "Set Item (세트아이템)",
  item_color: "Item Color (아이템 색상)",
  ego: "Spirit (정령)"
};

const SectionCard = ({ title, children, isOpen = true, onToggle }) => (
  <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden mb-4">
    <div 
      className="bg-gray-700/50 px-4 py-2 flex justify-between items-center cursor-pointer hover:bg-gray-700 transition-colors"
      onClick={onToggle}
    >
      <h3 className="text-sm font-bold text-orange-400 uppercase tracking-wider flex items-center gap-2">
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        {title}
      </h3>
    </div>
    {isOpen && <div className="p-4 space-y-3">{children}</div>}
  </div>
);

const Sell = () => {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [ocrResult, setOcrResult] = useState(null);
  const [detectedLines, setDetectedLines] = useState([]);
  const [openSections, setOpenSections] = useState({
    item_attrs: true,
    enchant: true,
    reforge: true,
    item_mod: true,
    erg: true,
    set_item: true,
    item_color: true
  });
  
  const [sessionId, setSessionId] = useState(null);

  const [formData, setFormData] = useState({
    name: '',
    price: '',
    category: 'weapon',
    description: '',
    sections: {}
  });

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setOcrResult(null);
      setDetectedLines([]);
    }
  };

  const toggleSection = (key) => {
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleScan = async () => {
    if (!file) return;

    setIsLoading(true);
    setLoadingStep('SEGMENTING');
    
    const formDataUpload = new FormData();
    formDataUpload.append('file', file);

    try {
      // Step 1: Segmentation and Initial OCR
      setLoadingStep('RECOGNIZING');
      const res = await fetch('http://localhost:8000/upload-item-v3', {
        method: 'POST',
        body: formDataUpload,
      });

      if (!res.ok) throw new Error('Failed to process image');

      const data = await res.json();
      setOcrResult(data);
      setDetectedLines(data.all_lines || []);
      setSessionId(data.session_id || null);

      // Map sections to form data
      const newSections = data.sections || {};
      
      // Auto-populate some core fields
      const itemName = newSections.item_name?.text || '';
      const allText = (data.all_lines || []).map(l => l.text).join('\n');
      
      setFormData(prev => ({
        ...prev,
        name: itemName,
        description: allText,
        sections: newSections
      }));

      setLoadingStep('COMPLETE');
      setTimeout(() => setLoadingStep(''), 2000);

    } catch (error) {
      console.error("Error processing image:", error);
      alert("Error scanning image. Please try again.");
      setLoadingStep('ERROR');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSectionTextChange = (sectionKey, lineIdx, newText) => {
    setFormData(prev => {
      const updatedSections = { ...prev.sections };
      if (updatedSections[sectionKey] && updatedSections[sectionKey].lines) {
        const updatedLines = [...updatedSections[sectionKey].lines];
        updatedLines[lineIdx] = { ...updatedLines[lineIdx], text: newText };
        updatedSections[sectionKey] = { ...updatedSections[sectionKey], lines: updatedLines };
      }
      return { ...prev, sections: updatedSections };
    });
  };

  const renderSectionContent = (key, sectionData) => {
    if (sectionData.skipped) return <p className="text-xs text-gray-500 italic">Section skipped by parser</p>;
    
    // Special handling for Color Parts
    if (key === 'item_color' && sectionData.parts) {
      return (
        <div className="grid grid-cols-3 gap-2">
          {sectionData.parts.map((p, idx) => (
            <div key={idx} className="bg-gray-900 p-2 rounded border border-gray-700 flex items-center gap-3">
              <div 
                className="w-8 h-8 rounded border border-white/20" 
                style={{ backgroundColor: `rgb(${p.r || 0}, ${p.g || 0}, ${p.b || 0})` }}
                title={`R:${p.r} G:${p.g} B:${p.b}`}
              />
              <div>
                <span className="text-xs font-bold text-gray-400">Part {p.part}</span>
                <div className="text-[10px] text-gray-500">
                  {p.r},{p.g},{p.b}
                </div>
              </div>
            </div>
          ))}
        </div>
      );
    }

    // Special handling for Enchant (prefix/suffix structure)
    if (key === 'enchant' && (sectionData.prefix || sectionData.suffix)) {
        const renderSlot = (slot, slotLabel) => {
            if (!slot) return null;
            return (
                <div className="bg-gray-900/50 p-3 rounded border border-gray-700">
                    <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-purple-300">{slot.name}</span>
                        <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded border border-purple-700/50">
                            {slotLabel} · Rank {slot.rank}
                        </span>
                    </div>
                    <div className="space-y-1.5 pl-3 border-l border-purple-900/30">
                        {slot.effects.map((eff, i) => (
                            <p key={i} className="text-xs text-gray-400">
                                <span className="text-gray-600 mr-1">-</span>
                                {eff.option_name != null ? (
                                    <>
                                        <span>{eff.option_name} </span>
                                        <span className="text-orange-400 font-bold">{eff.option_level}</span>
                                        {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim() && (
                                            <span> {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim()}</span>
                                        )}
                                    </>
                                ) : (
                                    <span>{eff.text}</span>
                                )}
                            </p>
                        ))}
                    </div>
                </div>
            );
        };

        return (
            <div className="space-y-3">
                {renderSlot(sectionData.prefix, 'Prefix')}
                {renderSlot(sectionData.suffix, 'Suffix')}
                {/* Fallback to raw lines if no structured data */}
                {!sectionData.prefix && !sectionData.suffix && sectionData.lines?.filter(l => !l.is_header).map((line, idx) => (
                    <input
                        key={idx}
                        type="text"
                        value={line.text}
                        onChange={(e) => handleSectionTextChange(key, idx, e.target.value)}
                        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none"
                    />
                ))}
            </div>
        );
    }

    // Special handling for Reforge Options
    if (key === 'reforge' && sectionData.options) {
        return (
            <div className="space-y-3">
                {sectionData.options.map((opt, idx) => (
                    <div key={idx} className="bg-gray-900/50 p-2 rounded border border-gray-700">
                        <div className="flex justify-between items-center mb-1">
                            <span className="text-sm font-medium text-cyan-300">{opt.option_name || opt.name}</span>
                            <span className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
                                Level {opt.option_level || opt.level} / {opt.max_level}
                            </span>
                        </div>
                        {opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
                    </div>
                ))}
                {/* Fallback to raw lines if options parsing failed */}
                {!sectionData.options.length && sectionData.lines?.map((line, idx) => (
                    <input
                        key={idx}
                        type="text"
                        value={line.text}
                        onChange={(e) => handleSectionTextChange(key, idx, e.target.value)}
                        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none"
                    />
                ))}
            </div>
        )
    }

    // Default: List of lines as inputs
    return (
      <div className="space-y-2">
        {(sectionData.lines || [])
          .filter(line => !line.is_header)
          .map((line, idx) => (
            <div key={idx} className="relative group">
              <input
                type="text"
                value={line.text}
                onChange={(e) => handleSectionTextChange(key, idx, e.target.value)}
                className={`w-full bg-gray-900 border ${line.confidence < 0.7 ? 'border-red-900/50 focus:border-red-500' : 'border-gray-700 focus:border-orange-500'} rounded px-3 py-1.5 text-sm text-gray-300 outline-none transition-colors`}
              />
              {line.confidence < 0.7 && (
                  <AlertTriangle className="w-3 h-3 text-red-500 absolute right-2 top-1/2 -translate-y-1/2 opacity-50 group-hover:opacity-100 transition-opacity" title={`Low Confidence: ${Math.round(line.confidence * 100)}%`} />
              )}
            </div>
          ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-4xl font-black text-white tracking-tight">SELL <span className="text-orange-500">ITEM</span></h1>
            <p className="text-gray-400 text-sm mt-1">Register your Mabinogi items via OCR</p>
          </div>
          <div className="flex gap-3">
             {loadingStep === 'COMPLETE' && <span className="flex items-center gap-1 text-green-400 text-sm font-bold bg-green-950/30 px-3 py-1 rounded-full border border-green-900/50"><CheckCircle2 className="w-4 h-4" /> Scan Successful</span>}
          </div>
        </header>
        
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          {/* Left Column: Image Upload (4 cols) */}
          <div className="xl:col-span-4 space-y-6">
            <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-2xl">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-orange-500" />
                Upload Tooltip
              </h2>
              
              {!previewUrl ? (
                <div className="border-2 border-dashed border-gray-700 rounded-xl h-80 flex flex-col items-center justify-center text-gray-500 hover:border-orange-500 hover:bg-orange-500/5 transition-all cursor-pointer relative group">
                  <input 
                    type="file" 
                    onChange={handleFileChange} 
                    accept="image/*"
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                  <div className="bg-gray-700 p-4 rounded-full mb-4 group-hover:scale-110 transition-transform">
                    <Upload className="w-8 h-8 text-gray-400" />
                  </div>
                  <span className="font-bold">Drop Mabinogi Screenshot</span>
                  <span className="text-xs mt-1 text-gray-600">Supports JPG, PNG</span>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="relative group">
                    <img 
                      src={previewUrl} 
                      alt="Item Preview" 
                      className="w-full rounded-xl shadow-xl border border-gray-700"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-xl">
                        <button 
                            onClick={() => { setFile(null); setPreviewUrl(null); setOcrResult(null); setDetectedLines([]); }}
                            className="bg-red-600 p-2 rounded-full hover:bg-red-700 text-white shadow-lg"
                        >
                            <X className="w-6 h-6" />
                        </button>
                    </div>
                  </div>
                </div>
              )}

              {file && !isLoading && (
                <button
                  onClick={handleScan}
                  className="w-full mt-6 bg-orange-600 hover:bg-orange-500 text-white py-4 rounded-xl flex items-center justify-center gap-2 font-black uppercase tracking-widest transition-all shadow-lg active:scale-95"
                >
                  <RotateCw className="w-5 h-5" />
                  Scan Tooltip
                </button>
              )}

              {isLoading && (
                <div className="w-full mt-6 bg-gray-700/50 text-gray-300 py-4 rounded-xl flex flex-col items-center justify-center gap-3 cursor-wait border border-gray-600">
                  <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
                  <div className="text-center">
                    <p className="font-bold text-sm tracking-wide">
                        {loadingStep === 'SEGMENTING' ? 'DETECTING SECTIONS...' : 
                         loadingStep === 'RECOGNIZING' ? 'READING TEXT STATS...' : 'PROCESSING...'}
                    </p>
                    <p className="text-[10px] text-gray-500 mt-1 uppercase">Attempt 17 (V3 Pipeline)</p>
                  </div>
                </div>
              )}
            </div>

            {/* Confidence Stats */}
            {ocrResult && (
                <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-xl">
                    <h3 className="text-xs font-black text-gray-500 uppercase tracking-widest mb-4">OCR METRICS</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gray-900/50 p-3 rounded-xl border border-gray-700/50">
                            <span className="text-[10px] text-gray-500 font-bold uppercase block mb-1">Total Lines</span>
                            <span className="text-2xl font-black text-white">{detectedLines.length}</span>
                        </div>
                        <div className="bg-gray-900/50 p-3 rounded-xl border border-gray-700/50">
                            <span className="text-[10px] text-gray-500 font-bold uppercase block mb-1">Sections</span>
                            <span className="text-2xl font-black text-orange-500">{Object.keys(ocrResult.sections).length}</span>
                        </div>
                    </div>
                </div>
            )}
          </div>

          {/* Right Column: Structured Form (8 cols) */}
          <div className="xl:col-span-8">
            <div className="bg-gray-800 rounded-2xl p-8 border border-gray-700 shadow-2xl relative overflow-hidden">
              {/* Header Accent */}
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-right from-orange-600 via-yellow-500 to-orange-600"></div>

              <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-black flex items-center gap-3">
                   ITEM DETAILS
                   {ocrResult && <span className="bg-green-500/10 text-green-500 text-[10px] px-2 py-1 rounded border border-green-500/20">SCANNED</span>}
                </h2>
                <div className="text-xs text-gray-500 font-bold">MABINOGI MARKETPLACE V1.0</div>
              </div>
              
              <form className="space-y-6" onSubmit={async (e) => {
                e.preventDefault();

                // Collect all lines with global_index + current text
                const lines = [];
                for (const secData of Object.values(formData.sections)) {
                  if (!secData.lines) continue;
                  for (const line of secData.lines) {
                    if (line.global_index != null) {
                      lines.push({ global_index: line.global_index, text: line.text });
                    }
                  }
                }

                try {
                  const res = await fetch('http://localhost:8000/register-item', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      session_id: sessionId,
                      name: formData.name,
                      price: formData.price,
                      category: formData.category,
                      lines,
                    }),
                  });
                  if (!res.ok) throw new Error('Failed to register item');
                  const result = await res.json();
                  const corrMsg = result.corrections_saved
                    ? ` (${result.corrections_saved} correction(s) captured for training)`
                    : '';
                  alert(`Item registered successfully.${corrMsg}`);
                } catch (err) {
                  console.error('Register item error:', err);
                  alert('Failed to register item.');
                }
              }}>
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                    <div className="md:col-span-8">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Item Name</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleInputChange}
                            placeholder="e.g. Dragon Blade"
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-lg font-bold text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                    <div className="md:col-span-4">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Price (Gold)</label>
                        <input
                            type="number"
                            name="price"
                            value={formData.price}
                            onChange={handleInputChange}
                            placeholder="0"
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-lg font-bold text-orange-400 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                </div>

                {/* Structured Sections Grid */}
                {ocrResult ? (
                    <div className="space-y-2 mt-8">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-4">Detected Categories</label>
                        
                        {/* Render known sections in a specific order if possible */}
                        {Object.keys(formData.sections).map((secKey) => {
                            if (['item_name', 'item_type', 'flavor_text', 'shop_price'].includes(secKey)) return null;
                            const sectionData = formData.sections[secKey];
                            return (
                                <SectionCard 
                                    key={secKey} 
                                    title={CATEGORY_LABELS[secKey] || secKey} 
                                    isOpen={openSections[secKey]}
                                    onToggle={() => toggleSection(secKey)}
                                >
                                    {renderSectionContent(secKey, sectionData)}
                                </SectionCard>
                            );
                        })}

                        {/* Special case for Item Type if not in card */}
                        {formData.sections.item_type && (
                            <div className="bg-gray-900/30 p-4 rounded-xl border border-gray-700/50 mt-4">
                                <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Item Classification</label>
                                <p className="text-sm text-gray-400 italic font-medium">{formData.sections.item_type.text}</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="py-20 flex flex-col items-center justify-center border-2 border-dashed border-gray-700 rounded-2xl bg-gray-900/20 text-gray-500">
                        <RotateCw className="w-12 h-12 mb-4 opacity-10" />
                        <p className="font-bold tracking-tight">Upload and scan an item tooltip to populate details</p>
                        <p className="text-xs mt-1">Structured parsing will automatically organize the data.</p>
                    </div>
                )}

                <div className="pt-8 mt-8 border-t border-gray-700 flex gap-4">
                  <button
                    type="submit"
                    className="flex-1 bg-green-600 hover:bg-green-500 text-white py-4 rounded-2xl flex items-center justify-center gap-2 font-black text-xl transition-all shadow-xl active:scale-95 uppercase tracking-widest"
                  >
                    <Save className="w-6 h-6" />
                    Register Item
                  </button>
                  <button
                    type="button"
                    className="px-6 bg-gray-700 hover:bg-gray-600 text-white rounded-2xl font-bold transition-all shadow-lg active:scale-95"
                    title="Reset Form"
                    onClick={() => {
                        setOcrResult(null);
                        setFormData({ name: '', price: '', category: 'weapon', description: '', sections: {} });
                    }}
                  >
                    <RotateCw className="w-5 h-5" />
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sell;