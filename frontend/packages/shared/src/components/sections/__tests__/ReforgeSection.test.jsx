import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ReforgeSection from '../ReforgeSection';

describe('ReforgeSection', () => {
  beforeEach(() => {
    window.REFORGE_OPTIONS_CONFIG = [];
  });

  it('renders option list', () => {
    const options = [
      { name: '스매시 대미지', level: 15, max_level: 20, line_index: 0 },
      { name: '크리티컬 대미지', level: 10, max_level: 20, line_index: 1 },
    ];
    const lines = [
      { text: '스매시 대미지 (15/20 레벨)', line_index: 0 },
      { text: '크리티컬 대미지 (10/20 레벨)', line_index: 1 },
    ];

    render(
      <ReforgeSection options={options} lines={lines} onLineChange={vi.fn()} />
    );

    expect(screen.getByText('스매시 대미지')).toBeInTheDocument();
    expect(screen.getByText('크리티컬 대미지')).toBeInTheDocument();
  });

  it('shows level and max_level', () => {
    const options = [
      { name: '스매시 대미지', level: 15, max_level: 20, line_index: 0 },
    ];
    const lines = [
      { text: '스매시 대미지 (15/20 레벨)', line_index: 0 },
    ];

    render(
      <ReforgeSection options={options} lines={lines} onLineChange={vi.fn()} />
    );

    // Level "15 / 20" is rendered across text nodes in a single span
    expect(screen.getByText(/Level\s+15/)).toBeInTheDocument();
    expect(screen.getByText(/20/)).toBeInTheDocument();
  });

  it('renders fallback text inputs with empty options', () => {
    const lines = [
      { text: '스매시 대미지 (15/20 레벨)' },
    ];

    render(
      <ReforgeSection options={[]} lines={lines} onLineChange={vi.fn()} />
    );

    const input = screen.getByDisplayValue('스매시 대미지 (15/20 레벨)');
    expect(input).toBeInTheDocument();
  });

  it('renders add button with no data', () => {
    render(
      <ReforgeSection options={[]} lines={[]} onLineChange={vi.fn()} />
    );
    // Should have the add reforge option button
    expect(screen.getByRole('button')).toBeInTheDocument();
  });
});
