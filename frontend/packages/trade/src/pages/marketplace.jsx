import React, { useState, useEffect } from 'react';
import { Search, ShoppingBag, Wand2, Hammer } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getItems as fetchItemsApi, getItemDetail } from '@mabi/shared/api/recommend';

const SLOT_LABELS = { 0: 'Prefix', 1: 'Suffix' };

const Marketplace = () => {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemDetail, setItemDetail] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchItems();
  }, []);

  useEffect(() => {
    if (selectedItem) {
      fetchDetail(selectedItem.id);
    } else {
      setItemDetail(null);
    }
  }, [selectedItem]);

  const fetchItems = async () => {
    try {
      const { data } = await fetchItemsApi();
      setItems(data);
    } catch (error) {
      console.error("Failed to fetch items:", error);
    }
  };

  const fetchDetail = async (itemId) => {
    try {
      const { data } = await getItemDetail(itemId);
      setItemDetail(data);
    } catch (error) {
      console.error("Failed to fetch item detail:", error);
      setItemDetail(null);
    }
  };

  const filteredItems = items.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
          <h1 className="text-3xl font-bold text-cyan-400 flex items-center gap-2">
            <ShoppingBag className="w-8 h-8" />
            {t('marketplace.title')}
          </h1>

          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder={t('marketplace.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-full py-2 pl-10 pr-4 text-gray-100 focus:ring-2 focus:ring-cyan-500 outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Item Grid */}
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredItems.length > 0 ? (
              filteredItems.map(item => (
                <div
                  key={item.id}
                  onClick={() => setSelectedItem(item)}
                  className={`bg-gray-800 p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${selectedItem?.id === item.id ? 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 'border-gray-700 hover:border-gray-600'}`}
                >
                  <h3 className="font-bold text-lg mb-3">{item.name}</h3>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {item.enchant_count > 0 && (
                      <span className="text-xs px-2 py-1 bg-purple-900/50 text-purple-300 rounded-full flex items-center gap-1">
                        <Wand2 className="w-3 h-3" />
                        {t('marketplace.enchants', { count: item.enchant_count })}
                      </span>
                    )}
                    {item.reforge_count > 0 && (
                      <span className="text-xs px-2 py-1 bg-cyan-900/50 text-cyan-300 rounded-full flex items-center gap-1">
                        <Hammer className="w-3 h-3" />
                        {t('marketplace.reforges', { count: item.reforge_count })}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{formatDate(item.created_at)}</p>
                </div>
              ))
            ) : (
              <div className="md:col-span-2 bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-12 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>{items.length === 0 ? t('marketplace.noItems') : t('marketplace.noResults')}</p>
              </div>
            )}
          </div>

          {/* Sidebar: Item Detail */}
          <div className="lg:col-span-1 space-y-6">
            {selectedItem && itemDetail ? (
              <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 sticky top-6">
                <h2 className="text-2xl font-bold mb-4">{itemDetail.name}</h2>

                {/* Enchants */}
                {itemDetail.enchants?.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-purple-400 mb-2 flex items-center gap-1">
                      <Wand2 className="w-4 h-4" />
                      {t('marketplace.enchantLabel')}
                    </h3>
                    <div className="space-y-2">
                      {itemDetail.enchants.map((enc, idx) => (
                        <div key={idx} className="bg-gray-900/50 p-3 rounded border border-gray-700">
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-sm font-medium text-purple-300">{enc.enchant_name}</span>
                            <span className="text-xs text-gray-400">{SLOT_LABELS[enc.slot] || enc.slot}</span>
                          </div>
                          {enc.effects?.length > 0 && (
                            <ul className="space-y-0.5">
                              {enc.effects.map((eff, i) => (
                                <li key={i} className="text-xs text-gray-400">
                                  {eff.raw_text}{eff.value != null && <span className="text-cyan-300 ml-1">({eff.value})</span>}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Reforge */}
                {itemDetail.reforge_options?.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-cyan-400 mb-2 flex items-center gap-1">
                      <Hammer className="w-4 h-4" />
                      {t('marketplace.reforgeLabel')}
                    </h3>
                    <div className="space-y-2">
                      {itemDetail.reforge_options.map((opt, idx) => (
                        <div key={idx} className="bg-gray-900/50 p-3 rounded border border-gray-700 flex justify-between items-center">
                          <span className="text-sm text-cyan-300">{opt.option_name}</span>
                          {opt.level != null && (
                            <span className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
                              Lv.{opt.level} / {opt.max_level}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-8 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>{t('marketplace.selectItem')}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Marketplace;
