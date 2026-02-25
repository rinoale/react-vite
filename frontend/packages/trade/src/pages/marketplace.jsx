import React, { useState, useEffect } from 'react';
import { Search, ShoppingBag, Sparkles, Filter } from 'lucide-react';
import { getItems as fetchItemsApi, getRecommendationsByItem } from '@mabi/shared/api/recommend';

const Marketplace = () => {
  const [items, setItems] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Fetch all items on mount
  useEffect(() => {
    fetchItems();
  }, []);

  // Fetch recommendations when an item is selected
  useEffect(() => {
    if (selectedItem) {
      fetchRecommendations(selectedItem.id);
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

  const fetchRecommendations = async (itemId) => {
    try {
      const { data } = await getRecommendationsByItem(itemId);
      setRecommendations(data);
    } catch (error) {
      console.error("Failed to fetch recommendations:", error);
    }
  };

  const filteredItems = items.filter(item => 
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
          <h1 className="text-3xl font-bold text-cyan-400 flex items-center gap-2">
            <ShoppingBag className="w-8 h-8" />
            Marketplace
          </h1>
          
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search for items..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-full py-2 pl-10 pr-4 text-gray-100 focus:ring-2 focus:ring-cyan-500 outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Item Grid */}
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredItems.map(item => (
              <div 
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`bg-gray-800 p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${selectedItem?.id === item.id ? 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 'border-gray-700 hover:border-gray-600'}`}
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-lg">{item.name}</h3>
                  <span className="text-xs px-2 py-1 bg-gray-700 rounded-full text-gray-300">
                    {item.category}
                  </span>
                </div>
                <p className="text-gray-400 text-sm line-clamp-2">{item.description}</p>
              </div>
            ))}
          </div>

          {/* Sidebar: Details & Recommendations */}
          <div className="lg:col-span-1 space-y-6">
            {selectedItem ? (
              <>
                {/* Selected Item Detail */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 sticky top-6">
                  <h2 className="text-2xl font-bold mb-2">{selectedItem.name}</h2>
                  <span className="inline-block bg-cyan-900/50 text-cyan-300 px-3 py-1 rounded-full text-sm mb-4">
                    {selectedItem.category}
                  </span>
                  <p className="text-gray-300 mb-6 leading-relaxed">
                    {selectedItem.description}
                  </p>
                  
                  <button className="w-full bg-cyan-600 hover:bg-cyan-700 text-white py-3 rounded-lg font-bold mb-6 transition-colors">
                    Buy Now
                  </button>

                  {/* Recommendations */}
                  <div className="border-t border-gray-700 pt-6">
                    <h3 className="text-lg font-semibold flex items-center gap-2 mb-4 text-purple-400">
                      <Sparkles className="w-5 h-5" />
                      Recommended for You
                    </h3>
                    
                    <div className="space-y-3">
                      {recommendations.length > 0 ? (
                        recommendations.map((rec, idx) => (
                          <div 
                            key={idx} 
                            onClick={() => setSelectedItem(rec.item)}
                            className="bg-gray-700/50 p-3 rounded-lg hover:bg-gray-700 cursor-pointer transition-colors"
                          >
                            <div className="flex justify-between items-center mb-1">
                              <span className="font-medium text-sm">{rec.item.name}</span>
                              <span className="text-xs text-green-400">
                                {Math.round(rec.score * 100)}% match
                              </span>
                            </div>
                            <p className="text-xs text-gray-400 line-clamp-1">{rec.item.description}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-gray-500">No recommendations found.</p>
                      )}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-8 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>Select an item to view details and recommendations</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Marketplace;
