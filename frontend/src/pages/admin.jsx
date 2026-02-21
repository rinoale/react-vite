import React, { useState, useEffect } from 'react';
import { Loader2, ChevronDown, ChevronRight, Info, Database, List, RefreshCw } from 'lucide-react';

const Admin = () => {
  const [summary, setSummary] = useState(null);
  const [entries, setEntries] = useState([]);
  const [links, setLinks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedEnchantId, setExpandedEnchantId] = useState(null);
  const [activeTab, setActiveTab] = useState('enchants'); // 'enchants', 'raw_links', 'raw_reforge'
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });

  useEffect(() => {
    fetchInitialData();
  }, [pagination.offset]);

  const fetchInitialData = async () => {
    setIsLoading(true);
    try {
      // Fetch summary
      const summaryRes = await fetch('http://localhost:8000/admin/summary');
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Fetch enchant entries
      const entriesRes = await fetch(`http://localhost:8000/admin/enchant-entries?limit=${pagination.limit}&offset=${pagination.offset}`);
      const entriesData = await entriesRes.json();
      setEntries(entriesData.rows || []);

      // Fetch links (limit to 500 to try and capture as many as possible)
      const linksRes = await fetch(`http://localhost:8000/admin/links?limit=500&offset=0`);
      const linksData = await linksRes.json();
      setLinks(linksData.rows || []);
    } catch (error) {
      console.error("Error fetching admin data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const getEnchantEffects = (enchantId) => {
    return links.filter(link => link.enchant_entry_id === enchantId)
      .sort((a, b) => (a.effect_order || 0) - (b.effect_order || 0));
  };

  const toggleEnchant = (id) => {
    setExpandedEnchantId(expandedEnchantId === id ? null : id);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-4xl font-black text-white tracking-tight uppercase">ADMIN <span className="text-cyan-500">DASHBOARD</span></h1>
            <p className="text-gray-400 text-sm mt-1">Database Validation & Maintenance</p>
          </div>
          {summary && (
            <div className="flex gap-4">
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">Enchants</span>
                <span className="text-lg font-bold text-cyan-400">{summary.enchant_entries}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">Links</span>
                <span className="text-lg font-bold text-cyan-400">{summary.enchant_links}</span>
              </div>
            </div>
          )}
        </header>

        {isLoading && !summary ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mb-4" />
            <p className="text-gray-400 font-bold tracking-widest uppercase">Initializing Database...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-8">
            {/* Enchant List with Effects */}
            <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
              <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <List className="w-5 h-5 text-cyan-500" />
                  ENCHANT ENTRIES
                </h2>
                <div className="flex items-center gap-4">
                   <button 
                    onClick={() => { setPagination(prev => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) })); }}
                    className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
                    disabled={pagination.offset === 0}
                   >
                     PREV
                   </button>
                   <span className="text-xs font-mono">
                     {pagination.offset + 1} - {pagination.offset + entries.length} / {summary?.enchant_entries || '...'}
                   </span>
                   <button 
                    onClick={() => { setPagination(prev => ({ ...prev, offset: prev.offset + prev.limit })); }}
                    className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
                    disabled={entries.length < pagination.limit}
                   >
                     NEXT
                   </button>
                   <button onClick={fetchInitialData} className="p-1 hover:text-cyan-400">
                      <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                   </button>
                </div>
              </div>

              <div className="divide-y divide-gray-700">
                {entries.map((entry) => {
                  const isExpanded = expandedEnchantId === entry.id;
                  const effects = getEnchantEffects(entry.id);
                  const hasEffectsFetched = effects.length > 0;

                  return (
                    <div key={entry.id} className="transition-colors hover:bg-gray-700/30">
                      <div 
                        className="px-6 py-4 flex items-center justify-between cursor-pointer"
                        onClick={() => toggleEnchant(entry.id)}
                      >
                        <div className="flex items-center gap-4">
                          {isExpanded ? <ChevronDown className="w-5 h-5 text-cyan-500" /> : <ChevronRight className="w-5 h-5 text-gray-500" />}
                          <div>
                            <span className={`text-xs font-bold uppercase mr-2 px-1.5 py-0.5 rounded ${entry.slot === 0 ? 'bg-blue-900/50 text-blue-300' : 'bg-red-900/50 text-red-300'}`}>
                              {entry.slot === 0 ? 'Prefix' : 'Suffix'}
                            </span>
                            <span className="text-lg font-black text-white">{entry.name}</span>
                            <span className="ml-3 text-sm text-gray-500">Rank {entry.rank}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">ID: {entry.id}</span>
                          <span className="text-xs font-bold text-cyan-600 uppercase tracking-tighter">{entry.effect_count} EFFECTS</span>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="px-16 py-4 bg-black/20 space-y-3">
                          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">Enchant Effects & Conditions</p>
                          {effects.length > 0 ? (
                            <ul className="space-y-3">
                              {effects.map((eff, idx) => (
                                <li key={idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50 flex flex-col gap-1">
                                  <div className="flex justify-between items-start">
                                    <span className="text-sm font-medium text-cyan-300">
                                      {eff.effect_text || eff.raw_text}
                                    </span>
                                    {eff.effect_direction !== null && (
                                      <span className={`text-[10px] font-bold uppercase px-1.5 rounded ${eff.effect_direction === 1 ? 'text-green-400 bg-green-900/20' : 'text-red-400 bg-red-900/20'}`}>
                                        {eff.effect_direction === 1 ? 'Bonus' : 'Penalty'}
                                      </span>
                                    )}
                                  </div>
                                  {eff.condition_text && (
                                    <p className="text-[11px] text-gray-500 flex items-center gap-1 italic">
                                      <Info className="w-3 h-3" />
                                      Condition: {eff.condition_text}
                                    </p>
                                  )}
                                  <div className="flex gap-4 mt-1">
                                     <span className="text-[10px] text-gray-600">Order: {eff.effect_order}</span>
                                     <span className="text-[10px] text-gray-600">Value: {eff.effect_value ?? 'N/A'}</span>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="py-4 text-center">
                              {isLoading ? (
                                <div className="flex items-center justify-center gap-2">
                                  <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                                  <span className="text-xs text-gray-600 uppercase">Searching links...</span>
                                </div>
                              ) : (
                                <p className="text-xs text-gray-600 uppercase">No effects cached. They might be in later link pages.</p>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;