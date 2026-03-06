import { useState, useRef, useEffect, useMemo } from 'react';
import { searchGameItemsLocal } from '@mabi/shared/lib/gameItems';

export function useGameItemSelector({ onSelect } = {}) {
  const [gameItemQuery, setGameItemQuery] = useState('');
  const [selectedGameItem, setSelectedGameItem] = useState(null);
  const [showGameItemSuggestions, setShowGameItemSuggestions] = useState(false);
  const gameItemRef = useRef(null);

  const gameItemSuggestions = useMemo(() => {
    if (!gameItemQuery.trim()) return [];
    return searchGameItemsLocal(gameItemQuery.trim());
  }, [gameItemQuery]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (gameItemRef.current && !gameItemRef.current.contains(e.target)) {
        setShowGameItemSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleGameItemSearch = (query) => {
    setGameItemQuery(query);
    setSelectedGameItem(null);
    setShowGameItemSuggestions(query.trim().length > 0);
  };

  const handleSelectGameItem = (gi) => {
    setSelectedGameItem(gi);
    setGameItemQuery(gi.name);
    setShowGameItemSuggestions(false);
    onSelect?.(gi);
  };

  const clearGameItem = () => {
    setSelectedGameItem(null);
    setGameItemQuery('');
  };

  return {
    gameItemQuery, selectedGameItem, showGameItemSuggestions,
    gameItemSuggestions, gameItemRef,
    handleGameItemSearch,
    handleSelectGameItem,
    clearGameItem,
    setShowGameItemSuggestions,
    setGameItemQuery,
    setSelectedGameItem,
  };
}
