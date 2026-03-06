import React, { useState, useCallback } from 'react';
import { Plus, RotateCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import SectionCard from './SectionCard';
import CustomSelect from './CustomSelect';
import { ColorPartsSection, EnchantSection, ErgSection, ItemAttrsSection, ItemModSection, ReforgeSection, SetItemSection, DefaultSection } from './sections';

const ADDABLE_SECTIONS = [
  'item_attrs', 'enchant', 'reforge', 'item_mod',
  'erg', 'set_item', 'item_color',
];

const HIDDEN_SECTIONS = ['item_name', 'item_type', 'flavor_text', 'shop_price', 'pre_header', 'ego', 'item_grade'];

function createEmptySection(secKey) {
  if (secKey === 'enchant') return { prefix: null, suffix: null, lines: [] };
  if (secKey === 'reforge') return { options: [], lines: [] };
  if (secKey === 'item_color') return { parts: [] };
  return { lines: [] };
}

const ItemDetailSections = ({ sections, onSectionsChange, abbreviated = true }) => {
  const { t } = useTranslation();
  const [openSections, setOpenSections] = useState({
    item_attrs: true,
    enchant: true,
    reforge: true,
    item_mod: true,
    erg: true,
    set_item: true,
    item_color: true,
  });

  const toggleSection = (key) => {
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSectionTextChange = (sectionKey, lineIdx, newText, structuredUpdate) => {
    const sec = { ...sections[sectionKey] };
    if (sec.lines) {
      const updatedLines = [...sec.lines];
      updatedLines[lineIdx] = { ...updatedLines[lineIdx], text: newText };
      sec.lines = updatedLines;
    }
    if (structuredUpdate) {
      structuredUpdate(sec);
    }
    onSectionsChange({ ...sections, [sectionKey]: sec });
  };

  const handleAddSection = (secKey) => {
    onSectionsChange({ ...sections, [secKey]: { ...createEmptySection(secKey), _added: true } });
    setOpenSections(prev => ({ ...prev, [secKey]: true }));
  };

  const handleRemoveSection = (secKey) => {
    const { [secKey]: _, ...rest } = sections;
    onSectionsChange(rest);
  };

  const handleAddSectionSelect = useCallback((val) => {
    if (val) handleAddSection(val);
  }, [sections]);

  const renderSectionContent = (key, sectionData) => {
    if (sectionData.skipped) return <p className="text-xs text-gray-500 italic">{t('sell.sectionSkipped')}</p>;

    const onLineChange = (lineIdx, newText, structuredUpdate) => handleSectionTextChange(key, lineIdx, newText, structuredUpdate);

    if (key === 'item_color' && sectionData.parts)
      return <ColorPartsSection parts={sectionData.parts} />;
    if (key === 'enchant')
      return <EnchantSection prefix={sectionData.prefix} suffix={sectionData.suffix} lines={sectionData.lines} onLineChange={onLineChange} abbreviated={abbreviated} />;
    if (key === 'item_attrs' && sectionData.attrs)
      return <ItemAttrsSection attrs={sectionData.attrs} onAttrsChange={(newAttrs) => {
        onSectionsChange({ ...sections, [key]: { ...sectionData, attrs: newAttrs } });
      }} />;
    if (key === 'reforge')
      return <ReforgeSection options={sectionData.options} lines={sectionData.lines} onLineChange={onLineChange} />;
    if (key === 'item_mod')
      return <ItemModSection lines={sectionData.lines} has_special_upgrade={sectionData.has_special_upgrade} special_upgrade_type={sectionData.special_upgrade_type} special_upgrade_level={sectionData.special_upgrade_level} onLineChange={onLineChange} />;
    if (key === 'erg')
      return <ErgSection lines={sectionData.lines} erg_grade={sectionData.erg_grade} erg_level={sectionData.erg_level} erg_max_level={sectionData.erg_max_level} onLineChange={onLineChange} />;
    if (key === 'set_item')
      return <SetItemSection lines={sectionData.lines} set_effects={sectionData.set_effects} onLineChange={onLineChange} />;
    return <DefaultSection lines={sectionData.lines} onLineChange={onLineChange} />;
  };

  const hasContent = (key, data) => {
    if (data.skipped) return false;
    if (data._added) return true;
    if (key === 'item_color') return data.parts?.length > 0;
    if (key === 'enchant') return data.prefix || data.suffix || data.lines?.length > 0;
    if (key === 'item_attrs') return data.attrs && Object.keys(data.attrs).length > 0;
    if (key === 'reforge') return data.options?.length > 0 || data.lines?.length > 0;
    if (key === 'item_mod') return data.has_special_upgrade || data.lines?.length > 0;
    if (key === 'erg') return data.erg_grade != null || data.lines?.length > 0;
    if (key === 'set_item') return data.set_effects?.length > 0 || data.lines?.length > 0;
    return data.lines?.length > 0;
  };

  const visibleKeys = Object.keys(sections).filter(k => !HIDDEN_SECTIONS.includes(k) && hasContent(k, sections[k]));
  const availableSections = ADDABLE_SECTIONS.filter(s => !visibleKeys.includes(s));

  return (
    <div className="space-y-2">
      {visibleKeys.map((secKey) => (
        <SectionCard
          key={secKey}
          title={t(`categoryLabels.${secKey}`, secKey)}
          isOpen={openSections[secKey]}
          onToggle={() => toggleSection(secKey)}
          onRemove={() => handleRemoveSection(secKey)}
        >
          {renderSectionContent(secKey, sections[secKey])}
        </SectionCard>
      ))}

      {sections.item_type && (
        <div className="bg-gray-900/30 p-4 rounded-xl border border-gray-700/50 mt-4">
          <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">{t('sell.itemClassification')}</label>
          <p className="text-sm text-gray-400 italic font-medium">{sections.item_type.text}</p>
        </div>
      )}

      {visibleKeys.length === 0 && (
        <div className="py-12 flex flex-col items-center justify-center border-2 border-dashed border-gray-700 rounded-2xl bg-gray-900/20 text-gray-500">
          <RotateCw className="w-10 h-10 mb-3 opacity-10" />
          <p className="font-bold tracking-tight text-sm">{t('sell.noSectionsYet')}</p>
        </div>
      )}

      {availableSections.length > 0 && (
        <div className="flex items-center gap-2 mt-4">
          <Plus className="w-4 h-4 text-gray-500" />
          <CustomSelect
            value=""
            onChange={handleAddSectionSelect}
            options={availableSections.map((s) => ({ value: s, label: t(`categoryLabels.${s}`, s) }))}
            placeholder={t('sell.addSectionPlaceholder')}
            triggerClassName="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-400 hover:border-gray-600 transition-colors"
          />
        </div>
      )}
    </div>
  );
};

export default ItemDetailSections;
