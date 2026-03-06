import React, { useState, useCallback } from 'react';
import { Upload, Loader2, Save, X, RotateCw, CheckCircle2, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useToast } from '@mabi/shared/components/useToast';
import InlineBanner from '@mabi/shared/components/InlineBanner';
import ItemDetailSections from '@mabi/shared/components/ItemDetailSections';
import CustomSelect from '@mabi/shared/components/CustomSelect';
import { registerListing } from '@mabi/shared/api/items';
import { buildRegistrationPayload } from '@mabi/shared/lib/registrationPayload';
import { useImageUpload } from '../hooks/useImageUpload';
import { useGameItemSelector } from '../hooks/useGameItemSelector';
import TagEditor from '../components/TagEditor';

const Sell = () => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [errorBanner, setErrorBanner] = useState(null);

  const [formData, setFormData] = useState({
    name: '',
    price: '',
    category: 'weapon',
    description: '',
    tags: [],
    sections: {}
  });

  const gameItem = useGameItemSelector({
    onSelect: (gi) => {
      setFormData(prev => ({ ...prev, name: prev.name || gi.name }));
    },
  });

  const upload = useImageUpload({
    onScanComplete: (result) => {
      // Auto-resolve game item
      if (result.parsedItemName) {
        if (result.gameItemMatch) {
          gameItem.setSelectedGameItem(result.gameItemMatch);
          gameItem.setGameItemQuery(result.gameItemMatch.name);
        } else {
          gameItem.setGameItemQuery(result.parsedItemName);
        }
      }
      setFormData(prev => ({
        ...prev,
        name: prev.name || result.itemName,
        sections: result.sections,
        abbreviated: result.abbreviated,
      }));
    },
    onScanError: () => {
      setErrorBanner(t('sell.errorScanning'));
    },
  });

  const handleDismissError = () => setErrorBanner(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handlePriceChange = (e) => {
    const raw = e.target.value.replace(/,/g, '');
    if (raw === '' || /^\d+$/.test(raw)) {
      setFormData(prev => ({ ...prev, price: raw }));
    }
  };

  const handleTagsChange = (newTags) => {
    setFormData(prev => ({ ...prev, tags: newTags }));
  };

  const handleSectionsChange = (newSections) => {
    setFormData(prev => ({ ...prev, sections: newSections }));
  };

  const handleGameItemSearchChange = useCallback((q) => {
    gameItem.handleGameItemSearch(q);
  }, [gameItem.handleGameItemSearch]);

  const handleGameItemSelect = useCallback((id) => {
    const gi = gameItem.gameItemSuggestions.find((g) => g.id === id);
    if (gi) gameItem.handleSelectGameItem(gi);
  }, [gameItem.gameItemSuggestions, gameItem.handleSelectGameItem]);

  const handleFormSubmit = (e) => {
    e.preventDefault();
    handleRegister();
  };

  const handleReset = () => {
    upload.resetUpload();
    setFormData({ name: '', price: '', category: 'weapon', description: '', tags: [], sections: {} });
    gameItem.clearGameItem();
  };

  const handleRegister = async () => {
    const missing = [];
    if (!gameItem.selectedGameItem) missing.push(t('sell.gameItem'));
    if (!formData.name.trim()) missing.push(t('sell.itemName'));
    if (!formData.price) missing.push(t('sell.price'));
    if (missing.length) {
      showToast({ type: 'warning', message: t('sell.requiredFields', { fields: missing.join(', ') }) });
      return;
    }

    setErrorBanner(null);
    const payload = buildRegistrationPayload({
      sessionId: upload.sessionId,
      name: formData.name,
      description: formData.description,
      price: formData.price,
      category: formData.category,
      gameItem: gameItem.selectedGameItem,
      sections: formData.sections,
      tags: formData.tags,
    });

    try {
      const { data: result } = await registerListing(payload);
      const corrMsg = result.corrections_saved
        ? t('sell.correctionsCapture', { count: result.corrections_saved })
        : '';
      showToast({ type: 'success', message: `${t('sell.itemRegistered')}${corrMsg}` });
      handleReset();
    } catch (err) {
      console.error('Register item error:', err);
      setErrorBanner(t('sell.registerFailed'));
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto">
        {errorBanner && <InlineBanner type="error" message={errorBanner} onDismiss={handleDismissError} />}
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-4xl font-black text-white tracking-tight">{t('sell.title')} <span className="text-orange-500">{t('sell.titleHighlight')}</span></h1>
            <p className="text-gray-400 text-sm mt-1">{t('sell.subtitle')}</p>
          </div>
          <div className="flex gap-3">
             {upload.loadingStep === 'COMPLETE' && <span className="flex items-center gap-1 text-green-400 text-sm font-bold bg-green-950/30 px-3 py-1 rounded-full border border-green-900/50"><CheckCircle2 className="w-4 h-4" /> {t('sell.scanSuccessful')}</span>}
          </div>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          {/* Left Column: Image Upload (4 cols) */}
          <div className="xl:col-span-4 space-y-6">
            <div className="bg-gray-800 rounded-2xl p-6 border border-gray-700 shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold flex items-center gap-2">
                  <Upload className="w-5 h-5 text-orange-500" />
                  {t('sell.uploadTooltip')}
                </h2>
                {upload.file && !upload.isLoading && (
                  <button
                    onClick={upload.handleScan}
                    className="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 font-black text-sm uppercase tracking-widest transition-all shadow-lg active:scale-95"
                  >
                    <RotateCw className="w-4 h-4" />
                    {t('sell.scanTooltip')}
                  </button>
                )}
                {upload.isLoading && (
                  <div className="flex items-center gap-2 text-gray-300">
                    <Loader2 className="w-5 h-5 text-orange-500 animate-spin" />
                    <span className="text-xs font-bold tracking-wide">
                      {upload.loadingStep === 'SEGMENTING' ? t('sell.detectingSections') :
                       upload.loadingStep === 'RECOGNIZING' ? t('sell.readingText') : t('sell.processing')}
                    </span>
                  </div>
                )}
              </div>

              {!upload.previewUrl ? (
                <div className="border-2 border-dashed border-gray-700 rounded-xl h-80 flex flex-col items-center justify-center text-gray-500 hover:border-orange-500 hover:bg-orange-500/5 transition-all cursor-pointer relative group">
                  <input
                    type="file"
                    onChange={upload.handleFileChange}
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
                      src={upload.previewUrl}
                      alt="Item Preview"
                      className="w-full rounded-xl shadow-xl border border-gray-700"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-xl">
                        <button
                            onClick={upload.clearImage}
                            className="bg-red-600 p-2 rounded-full hover:bg-red-700 text-white shadow-lg"
                        >
                            <X className="w-6 h-6" />
                        </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

          </div>

          {/* Right Column: Structured Form (8 cols) */}
          <div className="xl:col-span-8">
            <div className="bg-gray-800 rounded-2xl p-8 border border-gray-700 shadow-2xl relative overflow-hidden">
              {/* Header Accent */}
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-right from-orange-600 via-yellow-500 to-orange-600"></div>

              <div className="flex justify-between items-center mb-8">
                <h2 className="text-2xl font-black flex items-center gap-3">
                   {t('sell.itemDetails')}
                   {upload.ocrResult && <span className="bg-green-500/10 text-green-500 text-[10px] px-2 py-1 rounded border border-green-500/20">{t('sell.scanned')}</span>}
                </h2>
              </div>

              <form className="space-y-6" onSubmit={handleFormSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                    {/* Game item selector */}
                    <div className="md:col-span-5">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.gameItem')}</label>
                        <div className="relative">
                          <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500 w-4 h-4 z-10 pointer-events-none" />
                          <CustomSelect
                            searchable
                            searchValue={gameItem.gameItemQuery}
                            onSearchChange={handleGameItemSearchChange}
                            options={gameItem.selectedGameItem ? [] : gameItem.gameItemSuggestions.map((gi) => ({ value: gi.id, label: gi.name }))}
                            onChange={handleGameItemSelect}
                            placeholder={t('sell.gameItemPlaceholder')}
                            triggerClassName={`w-full bg-gray-900 border rounded-xl pl-10 pr-10 py-3 text-sm font-bold text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all ${gameItem.selectedGameItem ? 'border-green-700' : 'border-gray-700'}`}
                            dropdownClassName="rounded-lg max-h-60 border-gray-700"
                          />
                          {gameItem.selectedGameItem && (
                            <button
                              type="button"
                              onClick={gameItem.clearGameItem}
                              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white z-10"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                    </div>
                    {/* Listing name */}
                    <div className="md:col-span-4">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.itemName')}</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleInputChange}
                            placeholder={t('sell.itemNamePlaceholder')}
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm font-bold text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                    <div className="md:col-span-3">
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.price')}</label>
                        <input
                            type="text"
                            inputMode="numeric"
                            name="price"
                            value={formData.price ? Number(formData.price).toLocaleString() : ''}
                            onChange={handlePriceChange}
                            placeholder="0"
                            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-lg font-bold text-orange-400 focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                        />
                    </div>
                </div>

                {/* Tags */}
                <TagEditor tags={formData.tags} onTagsChange={handleTagsChange} />

                {/* Structured Sections Grid */}
                <div className="mt-8">
                  <ItemDetailSections
                    sections={formData.sections}
                    onSectionsChange={handleSectionsChange}
                    abbreviated={formData.abbreviated}
                  />
                </div>

                {/* Description */}
                <div className="mt-6">
                  <input
                    type="text"
                    name="description"
                    value={formData.description}
                    onChange={handleInputChange}
                    placeholder={t('sell.descriptionPlaceholder')}
                    maxLength={50}
                    className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:ring-2 focus:ring-orange-500 focus:border-transparent outline-none transition-all"
                  />
                </div>

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
                    onClick={handleReset}
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
