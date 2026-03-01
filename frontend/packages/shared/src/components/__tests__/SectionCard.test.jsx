import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SectionCard from '../SectionCard';

describe('SectionCard', () => {
  it('renders title and children when open', () => {
    render(
      <SectionCard title="인챈트" isOpen={true}>
        <p>효과 내용</p>
      </SectionCard>
    );
    expect(screen.getByText('인챈트')).toBeInTheDocument();
    expect(screen.getByText('효과 내용')).toBeInTheDocument();
  });

  it('hides children when collapsed', () => {
    render(
      <SectionCard title="인챈트" isOpen={false}>
        <p>효과 내용</p>
      </SectionCard>
    );
    expect(screen.getByText('인챈트')).toBeInTheDocument();
    expect(screen.queryByText('효과 내용')).not.toBeInTheDocument();
  });

  it('calls onToggle when header clicked', () => {
    const onToggle = vi.fn();
    render(<SectionCard title="인챈트" onToggle={onToggle} />);
    fireEvent.click(screen.getByText('인챈트'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('shows remove button when onRemove provided', () => {
    const onRemove = vi.fn();
    render(<SectionCard title="인챈트" onRemove={onRemove} />);
    const removeBtn = screen.getByTitle('Remove section');
    expect(removeBtn).toBeInTheDocument();
    fireEvent.click(removeBtn);
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('does not show remove button when onRemove not provided', () => {
    render(<SectionCard title="인챈트" />);
    expect(screen.queryByTitle('Remove section')).not.toBeInTheDocument();
  });
});
