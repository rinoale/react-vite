import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ConfigSearchInput from '../ConfigSearchInput';

const ITEMS = [
  { name: '스매시 대미지' },
  { name: '크리티컬 대미지' },
  { name: '매직 실드 방어' },
];

describe('ConfigSearchInput', () => {
  const defaultProps = {
    items: ITEMS,
    getLabel: (item) => item.name,
    onSelect: vi.fn(),
    onCancel: vi.fn(),
    placeholder: 'Search...',
  };

  it('renders input field', () => {
    render(<ConfigSearchInput {...defaultProps} />);
    expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
  });

  it('filters items on typing', () => {
    render(<ConfigSearchInput {...defaultProps} />);
    const input = screen.getByPlaceholderText('Search...');
    fireEvent.change(input, { target: { value: '대미지' } });
    expect(screen.getByText('스매시 대미지')).toBeInTheDocument();
    expect(screen.getByText('크리티컬 대미지')).toBeInTheDocument();
    expect(screen.queryByText('매직 실드 방어')).not.toBeInTheDocument();
  });

  it('calls onSelect when item clicked', () => {
    const onSelect = vi.fn();
    render(<ConfigSearchInput {...defaultProps} onSelect={onSelect} />);
    const input = screen.getByPlaceholderText('Search...');
    fireEvent.change(input, { target: { value: '스매시' } });
    fireEvent.click(screen.getByText('스매시 대미지'));
    expect(onSelect).toHaveBeenCalledWith(ITEMS[0]);
  });

  it('calls onCancel on Escape', () => {
    const onCancel = vi.fn();
    render(<ConfigSearchInput {...defaultProps} onCancel={onCancel} />);
    const input = screen.getByPlaceholderText('Search...');
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
