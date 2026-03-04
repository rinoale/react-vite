import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import EnchantSection from '../EnchantSection';

describe('EnchantSection', () => {
  beforeEach(() => {
    window.ENCHANTS_CONFIG = [];
  });

  it('renders prefix and suffix slots', () => {
    const prefix = {
      text: '[접두] 충격을 (랭크 F)',
      name: '충격을',
      rank: 'F',
      effects: [{ text: '최대대미지 15 증가', option_name: '최대대미지', option_level: 15 }],
    };
    const suffix = {
      text: '[접미] 관리자 (랭크 6)',
      name: '관리자',
      rank: '6',
      effects: [{ text: '방어 5 증가', option_name: '방어', option_level: 5 }],
    };
    const lines = [
      { text: '[접두] 충격을 (랭크 F)', line_index: 0 },
      { text: '최대대미지 15 증가', line_index: 1 },
      { text: '[접미] 관리자 (랭크 6)', line_index: 2 },
      { text: '방어 5 증가', line_index: 3 },
    ];

    render(
      <EnchantSection
        prefix={prefix}
        suffix={suffix}
        lines={lines}
        onLineChange={vi.fn()}
      />
    );

    expect(screen.getByText('충격을')).toBeInTheDocument();
    expect(screen.getByText('관리자')).toBeInTheDocument();
  });

  it('renders with empty data', () => {
    const { container } = render(
      <EnchantSection
        prefix={null}
        suffix={null}
        lines={[]}
        onLineChange={vi.fn()}
      />
    );
    // Should render add-slot buttons (Prefix and Suffix)
    expect(container.querySelector('div')).toBeInTheDocument();
  });

  it('shows rank and effects for prefix', () => {
    const prefix = {
      text: '[접두] 충격을 (랭크 F)',
      name: '충격을',
      rank: 'F',
      effects: [
        { text: '최대대미지 15 증가', option_name: '최대대미지', option_level: 15 },
        { text: '밸런스 3 % 증가', option_name: '밸런스', option_level: 3 },
      ],
    };
    const lines = [
      { text: '[접두] 충격을 (랭크 F)', line_index: 0 },
      { text: '최대대미지 15 증가', line_index: 1 },
      { text: '밸런스 3 % 증가', line_index: 2 },
    ];

    render(
      <EnchantSection
        prefix={prefix}
        suffix={null}
        lines={lines}
        onLineChange={vi.fn()}
      />
    );

    expect(screen.getByText('충격을')).toBeInTheDocument();
    // Rank "F" is embedded in "Prefix · Rank F" across text nodes
    expect(screen.getByText(/Rank\s+F/)).toBeInTheDocument();
    expect(screen.getByText('최대대미지')).toBeInTheDocument();
    expect(screen.getByText('밸런스')).toBeInTheDocument();
  });
});
