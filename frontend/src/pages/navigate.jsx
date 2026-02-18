import React, { useEffect, useRef, useState } from 'react';
import { Search, MapPin, Navigation, Crosshair } from 'lucide-react';

export default function SouthKoreaMap() {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [isGettingLocation, setIsGettingLocation] = useState(false);
  const [userLocation, setUserLocation] = useState(null);
  const searchMarkerRef = useRef(null);
  const userMarkerRef = useRef(null);

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

  // Auto-ask for location permission on map load
  useEffect(() => {
    if (mapReady && !userLocation && 'geolocation' in navigator) {
      // Small delay to ensure map is fully loaded
      setTimeout(() => {
        requestUserLocation(true); // Silent request (no error messages)
      }, 1000);
    }
  }, [mapReady]);

  // Update user marker when location changes
  useEffect(() => {
    if (!mapReady || !userLocation || !mapInstanceRef.current) return;

    // Remove previous user marker
    if (userMarkerRef.current) {
      mapInstanceRef.current.removeLayer(userMarkerRef.current);
    }

    // Create custom icon for user location
    const userIcon = window.L.divIcon({
      className: 'custom-user-marker',
      html: '<div style="background-color: #3b82f6; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.4);"></div>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });

    // Add user marker
    userMarkerRef.current = window.L.marker([userLocation.lat, userLocation.lng], { icon: userIcon })
      .addTo(mapInstanceRef.current)
      .bindPopup('<b>Your Location</b>');

    // Add accuracy circle if available
    if (userLocation.accuracy) {
      window.L.circle([userLocation.lat, userLocation.lng], {
        radius: userLocation.accuracy,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.1,
        weight: 2
      }).addTo(mapInstanceRef.current);
    }
  }, [mapReady, userLocation]);

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

  const requestUserLocation = async (silent = false) => {
    if (!('geolocation' in navigator)) {
      if (!silent) {
        setLocationError('Geolocation is not supported by your browser');
      }
      return;
    }

    setIsGettingLocation(true);
    if (!silent) {
      setLocationError('');
    }

    try {
      const position = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          resolve,
          reject,
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
          }
        );
      });

      const { latitude, longitude, accuracy } = position.coords;
      const location = {
        lat: latitude,
        lng: longitude,
        accuracy: accuracy
      };

      setUserLocation(location);

      // Zoom to user location
      if (mapInstanceRef.current) {
        mapInstanceRef.current.setView([latitude, longitude], 15, {
          animate: true,
          duration: 1
        });
      }

      if (!silent) {
        // Show success message briefly
        console.log('Location found successfully');
      }
    } catch (error) {
      let errorMessage = 'Unable to get your location';
      
      switch (error.code) {
        case error.PERMISSION_DENIED:
          errorMessage = 'Location access denied. Please allow location access.';
          break;
        case error.POSITION_UNAVAILABLE:
          errorMessage = 'Location information unavailable.';
          break;
        case error.TIMEOUT:
          errorMessage = 'Location request timed out.';
          break;
      }
      
      if (!silent) {
        setLocationError(errorMessage);
      }
    } finally {
      setIsGettingLocation(false);
    }
  };

  const zoomToUserLocation = () => {
    if (userLocation && mapInstanceRef.current) {
      mapInstanceRef.current.setView([userLocation.lat, userLocation.lng], 16, {
        animate: true,
        duration: 1
      });
      
      // Open user popup
      if (userMarkerRef.current) {
        userMarkerRef.current.openPopup();
      }
    } else {
      requestUserLocation();
    }
  };

  return (
    <div className="w-full h-screen flex flex-col">
      <div className="bg-blue-600 text-white p-4 shadow-lg">
        <h1 className="text-2xl font-bold">South Korea Navigation Map</h1>
        <p className="text-sm mt-1">Interactive map with address search and location services</p>
        
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
        
        {/* Location Controls */}
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => requestUserLocation()}
            disabled={isGettingLocation}
            className="bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 transition-colors"
          >
            <Navigation className="w-4 h-4" />
            {isGettingLocation ? 'Getting Location...' : 'Get My Location'}
          </button>
          
          {userLocation && (
            <button
              onClick={zoomToUserLocation}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 transition-colors"
            >
              <Crosshair className="w-4 h-4" />
              Zoom to My Location
            </button>
          )}
        </div>
        
        {/* Error Messages */}
        {(searchError || locationError) && (
          <div className="mt-2 space-y-1">
            {searchError && (
              <div className="bg-red-500 text-white px-3 py-2 rounded text-sm">
                {searchError}
              </div>
            )}
            {locationError && (
              <div className="bg-yellow-500 text-white px-3 py-2 rounded text-sm">
                {locationError}
              </div>
            )}
          </div>
        )}
      </div>
      
      <div className="relative flex-1">
        <div ref={mapRef} className="w-full h-full" style={{ height: '100%', minHeight: '400px' }} />
        
        {/* Floating Location Status */}
        {userLocation && (
          <div className="absolute top-4 left-4 bg-white text-gray-800 px-3 py-2 rounded-lg shadow-lg text-sm flex items-center gap-2 z-10">
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
            <span>Location Active</span>
          </div>
        )}
        
        {/* Location Permission Request Tooltip */}
        {!userLocation && mapReady && (
          <div className="absolute bottom-4 left-4 bg-yellow-100 border border-yellow-300 text-yellow-800 px-3 py-2 rounded-lg shadow-lg text-sm max-w-xs z-10">
            <p className="font-medium mb-1">📍 Enable Location Services</p>
            <p className="text-xs">Click "Get My Location" to see your position on the map</p>
          </div>
        )}
      </div>
      
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <p className="text-gray-600">Loading map...</p>
        </div>
      )}
    </div>
  );
}
