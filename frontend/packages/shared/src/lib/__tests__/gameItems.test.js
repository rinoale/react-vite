import { describe, it, expect, beforeEach } from 'vitest';
import {
  getGameItemsConfig,
  findGameItemByName,
  searchGameItemsLocal,
} from '../gameItems';

const MOCK_ITEMS = [
  { name: '다이아몬드 롱소드', category: '양손 검' },
  { name: '페넌스 체인블레이드', category: '체인블레이드' },
  { name: '가시 니들', category: '너클' },
  { name: '다이아몬드 단검', category: '단검' },
  { name: '레더 롱보우', category: '활' },
];

describe('gameItems', () => {
  beforeEach(() => {
    window.GAME_ITEMS_CONFIG = MOCK_ITEMS;
  });

  describe('getGameItemsConfig', () => {
    it('returns items from window config', () => {
      expect(getGameItemsConfig()).toBe(MOCK_ITEMS);
    });

    it('returns empty array when window var missing', () => {
      delete window.GAME_ITEMS_CONFIG;
      expect(getGameItemsConfig()).toEqual([]);
    });
  });

  describe('findGameItemByName', () => {
    it('finds exact match', () => {
      const result = findGameItemByName('가시 니들');
      expect(result).toEqual({ name: '가시 니들', category: '너클' });
    });

    it('returns undefined for no match', () => {
      expect(findGameItemByName('존재하지 않는 아이템')).toBeUndefined();
    });
  });

  describe('searchGameItemsLocal', () => {
    it('finds partial match', () => {
      const results = searchGameItemsLocal('다이아몬드');
      expect(results).toHaveLength(2);
      expect(results[0].name).toBe('다이아몬드 롱소드');
      expect(results[1].name).toBe('다이아몬드 단검');
    });

    it('respects limit param', () => {
      const results = searchGameItemsLocal('다이아몬드', 1);
      expect(results).toHaveLength(1);
    });

    it('case insensitive search', () => {
      window.GAME_ITEMS_CONFIG = [{ name: 'Diamond Sword' }];
      const results = searchGameItemsLocal('diamond');
      expect(results).toHaveLength(1);
    });

    it('returns empty for no match', () => {
      expect(searchGameItemsLocal('zzzzz')).toEqual([]);
    });
  });
});
