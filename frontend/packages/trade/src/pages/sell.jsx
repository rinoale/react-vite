import React, { useState, useRef, useEffect } from 'react';
import { Upload, Loader2, Save, X, Settings, RotateCw, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import SectionCard from '@mabi/shared/components/SectionCard';
import { ColorPartsSection, EnchantSection, ReforgeSection, DefaultSection } from '@mabi/shared/components/sections';
import { uploadItemV3, registerItem } from '@mabi/shared/api/items';

const Sell = () => {
  const { t } = useTranslation();
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

    try {
      // Step 1: Segmentation and Initial OCR
      setLoadingStep('RECOGNIZING');
      const { data } = await uploadItemV3(file);
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
      alert(t('sell.errorScanning'));
      setLoadingStep('ERROR');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSectionTextChange = (sectionKey, lineIdx, newText, structuredUpdate) => {
    setFormData(prev => {
      const sec = { ...prev.sections[sectionKey] };
      if (sec.lines) {
        const updatedLines = [...sec.lines];
        updatedLines[lineIdx] = { ...updatedLines[lineIdx], text: newText };
        sec.lines = updatedLines;
      }
      if (structuredUpdate) {
        structuredUpdate(sec);
      }
      return { ...prev, sections: { ...prev.sections, [sectionKey]: sec } };
    });
  };


  const renderSectionContent = (key, sectionData) => {
    if (sectionData.skipped) return <p className="text-xs text-gray-500 italic">{t('sell.sectionSkipped')}</p>;

    const onLineChange = (lineIdx, newText, structuredUpdate) => handleSectionTextChange(key, lineIdx, newText, structuredUpdate);

    if (key === 'item_color' && sectionData.parts)
      return <ColorPartsSection parts={sectionData.parts} />;
    if (key === 'enchant' && (sectionData.prefix || sectionData.suffix))
      return <EnchantSection prefix={sectionData.prefix} suffix={sectionData.suffix} lines={sectionData.lines} onLineChange={onLineChange} />;
    if (key === 'reforge' && sectionData.options)
      return <ReforgeSection options={sectionData.options} lines={sectionData.lines} onLineChange={onLineChange} />;
    return <DefaultSection lines={sectionData.lines} onLineChange={onLineChange} />;
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-4xl font-black text-white tracking-tight">{t('sell.title')} <span className="text-orange-500">{t('sell.titleHighlight')}</span></h1>
            <p className="text-gray-400 text-sm mt-1">{t('sell.subtitle')}</p>
          </div>
          <div className="flex gap-3">
             {loadingStep === 'COMPLETE' && <span className="flex items-center gap-1 text-green-400 text-sm font-bold bg-green-950/30 px-3 py-1 rounded-full border border-green-900/50"><CheckCircle2 className="w-4 h-4" /> {t('sell.scanSuccessful')}</span>}
          </div>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          {/* Left Column: Image Upload (4 cols) */}
          <div className="xl:col-span-4 space-y-6">
            <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-2xl">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Upload className="w-5 h-5 text-orange-500" />
                {t('sell.uploadTooltip')}
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
                  <span className="font-bold">{t('sell.dropScreenshot')}</span>
                  <span className="text-xs mt-1 text-gray-600">{t('sell.supportedFormats')}</span>
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
                  {t('sell.scanTooltip')}
                </button>
              )}

              {isLoading && (
                <div className="w-full mt-6 bg-gray-700/50 text-gray-300 py-4 rounded-xl flex flex-col items-center justify-center gap-3 cursor-wait border border-gray-600">
                  <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
                  <div className="text-center">
                    <p className="font-bold text-sm tracking-wide">
                        {loadingStep === 'SEGMENTING' ? t('sell.detectingSections') :
                         loadingStep === 'RECOGNIZING' ? t('sell.readingText') : t('sell.processing')}
                    </p>
                    <p className="text-[10px] text-gray-500 mt-1 uppercase">{t('sell.pipelineVersion')}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Confidence Stats */}
            {ocrResult && (
                <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-xl">
                    <h3 className="text-xs font-black text-gray-500 uppercase tracking-widest mb-4">{t('sell.ocrMetrics')}</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-gray-900/50 p-3 rounded-xl border border-gray-700/50">
                            <span className="text-[10px] text-gray-500 font-bold uppercase block mb-1">{t('sell.totalLines')}</span>
                            <span className="text-2xl font-black text-white">{detectedLines.length}</span>
                        </div>
                        <div className="bg-gray-900/50 p-3 rounded-xl border border-gray-700/50">
                            <span className="text-[10px] text-gray-500 font-bold uppercase block mb-1">{t('sell.sections')}</span>
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
                   {t('sell.itemDetails')}
                   {ocrResult && <span className="bg-green-500/10 text-green-500 text-[10px] px-2 py-1 rounded border border-green-500/20">{t('sell.scanned')}</span>}
                </h2>
                <div className="text-xs text-gray-500 font-bold">{t('sell.appVersion')}</div>
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

                // Extract structured enchant data
                const enchants = [];
                const enchantSec = formData.sections?.enchant;
                if (enchantSec?.prefix?.name) {
                  enchants.push({ slot: 0, name: enchantSec.prefix.name, rank: enchantSec.prefix.rank || '', effects: enchantSec.prefix.effects || [] });
                }
                if (enchantSec?.suffix?.name) {
                  enchants.push({ slot: 1, name: enchantSec.suffix.name, rank: enchantSec.suffix.rank || '', effects: enchantSec.suffix.effects || [] });
                }

                // Extract structured reforge data
                const reforge_options = (formData.sections?.reforge?.options || []).map(opt => ({
                  name: opt.option_name || opt.name || '',
                  level: opt.option_level ?? opt.level ?? null,
                  max_level: opt.max_level ?? null,
                }));

                try {
                  const { data: result } = await registerItem({
                    session_id: sessionId,
                    name: formData.name,
                    price: formData.price,
                    category: formData.category,
                    lines,
                    enchants,
                    reforge_options,
                  });
                  const corrMsg = result.corrections_saved
                    ? t('sell.correctionsCapture', { count: result.corrections_saved })
                    : '';
                  alert(`${t('sell.itemRegistered')}${corrMsg}`);
                } catch (err) {
                  console.error('Register item error:', err);
                  alert(t('sell.registerFailed'));
                }
              }}>
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                    <div className="md:col-span-8">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.itemName')}</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleInputChange}
                            placeholder={t('sell.itemNamePlaceholder')}
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-lg font-bold text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                    <div className="md:col-span-4">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.price')}</label>
                        <input
                            type="text"
                            inputMode="numeric"
                            name="price"
                            value={formData.price ? Number(formData.price).toLocaleString() : ''}
                            onChange={(e) => {
                              const raw = e.target.value.replace(/,/g, '');
                              if (raw === '' || /^\d+$/.test(raw)) {
                                setFormData(prev => ({ ...prev, price: raw }));
                              }
                            }}
                            placeholder="0"
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-lg font-bold text-orange-400 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                </div>

                {/* Structured Sections Grid */}
                {ocrResult ? (
                    <div className="space-y-2 mt-8">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-4">{t('sell.detectedCategories')}</label>

                        {/* Render known sections in a specific order if possible */}
                        {Object.keys(formData.sections).map((secKey) => {
                            if (['item_name', 'item_type', 'flavor_text', 'shop_price'].includes(secKey)) return null;
                            const sectionData = formData.sections[secKey];
                            return (
                                <SectionCard
                                    key={secKey}
                                    title={t(`categoryLabels.${secKey}`, secKey)}
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
                                <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.itemClassification')}</label>
                                <p className="text-sm text-gray-400 italic font-medium">{formData.sections.item_type.text}</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="py-20 flex flex-col items-center justify-center border-2 border-dashed border-gray-700 rounded-2xl bg-gray-900/20 text-gray-500">
                        <RotateCw className="w-12 h-12 mb-4 opacity-10" />
                        <p className="font-bold tracking-tight">{t('sell.emptyTitle')}</p>
                        <p className="text-xs mt-1">{t('sell.emptySubtitle')}</p>
                    </div>
                )}

                <div className="pt-8 mt-8 border-t border-gray-700 flex gap-4">
                  <button
                    type="submit"
                    className="flex-1 bg-green-600 hover:bg-green-500 text-white py-4 rounded-2xl flex items-center justify-center gap-2 font-black text-xl transition-all shadow-xl active:scale-95 uppercase tracking-widest"
                  >
                    <Save className="w-6 h-6" />
                    {t('sell.registerItem')}
                  </button>
                  <button
                    type="button"
                    className="px-6 bg-gray-700 hover:bg-gray-600 text-white rounded-2xl font-bold transition-all shadow-lg active:scale-95"
                    title={t('sell.resetForm')}
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
