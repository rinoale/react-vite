import React from 'react';
import { Hammer } from 'lucide-react';
import EchostoneIcon from '../components/icons/EchostoneIcon';
import MuriasRelicIcon from '../components/icons/MuriasRelicIcon';

export const ECHOSTONE_COLOR_MAP = {
  '레드 에코스톤': 'red', '블루 에코스톤': 'blue',
  '옐로 에코스톤': 'yellow', '블랙 에코스톤': 'black', '실버 에코스톤': 'silver',
};

export const ATTR_LABELS = {
  damage: '공격력', magic_damage: '마법공격력', additional_damage: '추가대미지',
  balance: '밸런스', defense: '방어', protection: '보호',
  magic_defense: '마법방어', magic_protection: '마법보호',
  durability: '내구력', piercing_level: '관통 레벨',
};

export const SLOT_LABELS = { 0: 'Prefix', 1: 'Suffix' };

export const getOptionIcon = (optionType, gameItemName) => {
  if (optionType === 'echostone_options') {
    const color = ECHOSTONE_COLOR_MAP[gameItemName] || 'red';
    return <EchostoneIcon color={color} className="w-4 h-4" />;
  }
  if (optionType === 'murias_relic_options') return <MuriasRelicIcon className="w-4 h-4" />;
  return <Hammer className="w-4 h-4" />;
};

export const getListingOptionDisplay = (opt, gameItemName) => {
  if (opt.option_type === 'murias_relic_options') {
    const cfg = (window.MURIAS_RELIC_CONFIG || []).find(c => c.option_name === opt.option_name);
    if (cfg?.value_per_level != null && opt.rolled_value != null) {
      const computed = +(cfg.value_per_level * +opt.rolled_value).toFixed(2);
      return `${opt.option_name} ${computed}${cfg.option_unit || ''}`;
    }
  }
  return opt.option_name;
};

const RANGE_RE = /\d+\s*~\s*\d+/;

export const rollColor = (eff) => {
  const { value, min_value, max_value, raw_text } = eff;
  if (value == null || min_value == null || max_value == null) return null;
  if (+min_value === +max_value) return null;

  const isMax = +value === +max_value;
  if (raw_text?.includes('피어싱 레벨')) return isMax ? 'text-red-400' : 'text-green-400';
  if (isMax) return 'text-red-400';

  const pct = (+value - +min_value) / (+max_value - +min_value);
  if (pct >= 0.8) return 'text-orange-400';
  if (pct >= 0.3) return 'text-blue-400';
  return 'text-green-400';
};

export const renderRolledEffect = (eff) => {
  const fixed = eff.min_value == null || eff.max_value == null || +eff.min_value === +eff.max_value;
  const hasRoll = !fixed && eff.value != null;
  const color = hasRoll ? rollColor(eff) : null;

  if (!hasRoll) return eff.raw_text;

  return (
    <>
      {eff.raw_text.split(RANGE_RE).map((part, pi, arr) =>
        pi < arr.length - 1 ? (
          <span key={pi}>{part}<span className={`font-bold ${color}`}>{eff.value}</span></span>
        ) : part
      )}
      <span className="text-gray-600 ml-1">({eff.min_value}~{eff.max_value})</span>
    </>
  );
};

export const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString();
};
