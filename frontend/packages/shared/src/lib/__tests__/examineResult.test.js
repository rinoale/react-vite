import { describe, it, expect, beforeEach } from 'vitest';
import { parseExamineResult } from '../examineResult';

describe('parseExamineResult', () => {
  beforeEach(() => {
    window.GAME_ITEMS_CONFIG = [
      { name: '다이아몬드 롱소드', category: '양손 검' },
    ];
  });

  it('parses full response with all fields', () => {
    const data = {
      session_id: 'abc123',
      abbreviated: false,
      sections: {
        pre_header: {
          item_name: '다이아몬드 롱소드',
          lines: [{ text: '축복받은 다이아몬드 롱소드' }],
        },
        item_attrs: {
          lines: [
            { text: '공격 10~20' },
            { text: '크리티컬 5' },
          ],
        },
      },
    };

    const result = parseExamineResult(data);
    expect(result.itemName).toBe('다이아몬드 롱소드');
    expect(result.parsedItemName).toBe('다이아몬드 롱소드');
    expect(result.sessionId).toBe('abc123');
    expect(result.abbreviated).toBe(false);
    expect(result.gameItemMatch).toEqual({ name: '다이아몬드 롱소드', category: '양손 검' });
    expect(result.description).toContain('축복받은 다이아몬드 롱소드');
    expect(result.description).toContain('공격 10~20');
  });

  it('handles empty sections', () => {
    const result = parseExamineResult({ sections: {} });
    expect(result.itemName).toBe('');
    expect(result.description).toBe('');
    expect(result.sessionId).toBeNull();
    expect(result.gameItemMatch).toBeNull();
  });

  it('handles missing session_id', () => {
    const result = parseExamineResult({ sections: {} });
    expect(result.sessionId).toBeNull();
  });

  it('defaults abbreviated to true when missing', () => {
    const result = parseExamineResult({ sections: {} });
    expect(result.abbreviated).toBe(true);
  });

  it('falls back to item_name.text when no pre_header.item_name', () => {
    const data = {
      sections: {
        item_name: { text: '가시 니들' },
      },
    };
    const result = parseExamineResult(data);
    expect(result.itemName).toBe('가시 니들');
    expect(result.parsedItemName).toBe('');
  });
});
