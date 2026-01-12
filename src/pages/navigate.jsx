import React, { useEffect, useRef, useState } from 'react';
import { Search, MapPin } from 'lucide-react';

export default function SouthKoreaMap() {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const searchMarkerRef = useRef(null);

  useEffect(() => {
    // Check if Leaflet is already loaded
    if (window.L) {
      setMapReady(true);
      return;
    }

    // Add required Leaflet styles to document
    const style = document.createElement('style');
    style.textContent = `
      .leaflet-container { 
        height: 100%; 
        width: 100%; 
      }
    `;
    document.head.appendChild(style);

    // Load Leaflet CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css';
    link.integrity = 'sha512-Zcn6bjR/8RZbLEpLIeOwNtzREBAJnUKESxces60Mpoj+2okopSAcSUIUOseddDm0cxnGQzxIR7vJgsLZbdLE3w==';
    link.crossOrigin = 'anonymous';
    link.referrerPolicy = 'no-referrer';
    document.head.appendChild(link);

    // Load Leaflet JS
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js';
    script.integrity = 'sha512-BwHfrr4c9kmRkLw6iXFdzcdWV/PGkVgiIyIWLLlTSXzWQzxuSg4DiQUCpauz/EWjgk5TYQqX/kvn9pG1NpYfqg==';
    script.crossOrigin = 'anonymous';
    script.referrerPolicy = 'no-referrer';
    script.onload = () => setMapReady(true);
    script.onerror = () => {
      console.error('Failed to load Leaflet');
      setSearchError('Failed to load map library. Please refresh the page.');
    };
    document.body.appendChild(script);

    return () => {
      if (link.parentNode) document.head.removeChild(link);
      if (script.parentNode) document.body.removeChild(script);
      if (style.parentNode) document.head.removeChild(style);
    };
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;

    // Initialize map centered on South Korea
    const map = window.L.map(mapRef.current).setView([36.5, 127.5], 7);
    mapInstanceRef.current = map;

    // Add OpenStreetMap tiles
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    // Add major city markers
    const cities = [
      { name: 'Seoul', lat: 37.5665, lng: 126.9780 },
      { name: 'Busan', lat: 35.1796, lng: 129.0756 },
      { name: 'Incheon', lat: 37.4563, lng: 126.7052 },
      { name: 'Daegu', lat: 35.8714, lng: 128.6014 },
      { name: 'Daejeon', lat: 36.3504, lng: 127.3845 },
      { name: 'Gwangju', lat: 35.1595, lng: 126.8526 },
      { name: 'Ulsan', lat: 35.5384, lng: 129.3114 },
      { name: 'Jeju City', lat: 33.4996, lng: 126.5312 },
    ];

    cities.forEach(city => {
      window.L.marker([city.lat, city.lng])
        .addTo(map)
        .bindPopup(`<b>${city.name}</b>`);
    });

    // Cleanup
    return () => {
      map.remove();
    };
  }, [mapReady]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    setSearchError('');

    try {
      // Using Nominatim API for geocoding
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&countrycodes=kr&limit=1`
      );
      const data = await response.json();

      if (data.length > 0) {
        const result = data[0];
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);

        // Remove previous search marker if exists
        if (searchMarkerRef.current) {
          mapInstanceRef.current.removeLayer(searchMarkerRef.current);
        }

        // Create custom icon for search result
        const searchIcon = window.L.divIcon({
          className: 'custom-search-marker',
          html: '<div style="background-color: #ef4444; width: 30px; height: 30px; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); border: 3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.3);"></div>',
          iconSize: [30, 30],
          iconAnchor: [15, 30],
        });

        // Add new search marker
        searchMarkerRef.current = window.L.marker([lat, lng], { icon: searchIcon })
          .addTo(mapInstanceRef.current)
          .bindPopup(`<b>${result.display_name}</b>`)
          .openPopup();

        // Zoom to location
        mapInstanceRef.current.setView([lat, lng], 15, {
          animate: true,
          duration: 1
        });
      } else {
        setSearchError('Location not found. Please try a different search term.');
      }
    } catch (error) {
      setSearchError('Error searching for location. Please try again.');
      console.error('Search error:', error);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="w-full h-screen flex flex-col">
      <div className="bg-blue-600 text-white p-4 shadow-lg">
        <h1 className="text-2xl font-bold">South Korea Navigation Map</h1>
        <p className="text-sm mt-1">Interactive map with address search</p>
        
        {/* Search Bar */}
        <form onSubmit={handleSearch} className="mt-4 flex gap-2">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for an address or place in South Korea..."
              className="w-full px-4 py-2 pr-10 rounded-lg text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <MapPin className="absolute right-3 top-2.5 text-gray-400" size={20} />
          </div>
          <button
            type="submit"
            disabled={searching || !searchQuery.trim()}
            className="bg-white text-blue-600 px-6 py-2 rounded-lg font-semibold hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
          >
            <Search size={20} />
            {searching ? 'Searching...' : 'Search'}
          </button>
        </form>
        
        {searchError && (
          <div className="mt-2 bg-red-500 text-white px-3 py-2 rounded text-sm">
            {searchError}
          </div>
        )}
      </div>
      
      <div ref={mapRef} className="flex-1 w-full relative" style={{ height: '100%', minHeight: '400px' }} />
      
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <p className="text-gray-600">Loading map...</p>
        </div>
      )}
    </div>
  );
}
