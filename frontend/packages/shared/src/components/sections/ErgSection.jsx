import React, { useState, useCallback } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import CustomSelect from '../CustomSelect';
import { editNumber } from '../../styles';

const GRADES = ['S', 'A', 'B'];
const MAX_LEVEL = 50;

const GRADE_OPTIONS = GRADES.map((g) => ({ value: g, label: g }));

const GRADE_TEXT = {
  S: 'text-pink-300',
  A: 'text-cyan-300',
  B: 'text-gray-300',
};

const NumberField = ({ value, onCommit, placeholder }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const commit = (raw) => {
    setEditing(false);
    onCommit(raw);
  };

  if (editing) {
    return (
      <input
        type="text"
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => commit(draft)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit(draft);
          if (e.key === 'Escape') setEditing(false);
        }}
        className={editNumber}
      />
    );
  }

  return (
    <span
      className="text-orange-400 font-bold cursor-pointer hover:underline"
      onClick={() => { setDraft(value != null ? String(value) : ''); setEditing(true); }}
    >
      {value ?? placeholder ?? '?'}
    </span>
  );
};

const ErgGradeRow = ({ grade, level, maxLevel, hasLines, onLineChange }) => {
  const { t } = useTranslation();
  const needsCorrection = hasLines && (grade === null || level === null);

  const update = (newGrade, newLevel, newMaxLevel) => {
    onLineChange(-1, '', (sec) => {
      sec.erg_grade = newGrade;
      sec.erg_level = newLevel;
      sec.erg_max_level = newMaxLevel;
    });
  };

  const handleGradeChange = useCallback((val) => {
    update(val || null, level, maxLevel);
  }, [level, maxLevel]);

  const gradeColor = GRADE_TEXT[grade] || GRADE_TEXT.B;
  const textColor = needsCorrection ? 'text-amber-200' : 'text-gray-300';

  return (
    <div className="p-2">
      {needsCorrection && (
        <div className="flex items-center gap-1.5 mb-1">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <p className="text-xs text-amber-300">{t('sections.erg.unrecognized')}</p>
        </div>
      )}
      <div className={`text-sm font-medium ${textColor}`}>
        {t('sections.erg.gradeLabel') + ' '}
        <CustomSelect
          value={grade || ''}
          onChange={handleGradeChange}
          options={GRADE_OPTIONS}
          placeholder="—"
          variant="inline"
          triggerClassName={`${needsCorrection ? 'text-amber-300' : gradeColor} font-bold`}
        />
        {' ('}
        <NumberField
          value={level}
          onCommit={(raw) => {
            const n = parseInt(raw, 10);
            if (!isNaN(n)) update(grade, Math.max(1, Math.min(MAX_LEVEL, n)), maxLevel);
          }}
          placeholder="—"
        />
        {'/'}
        <NumberField
          value={maxLevel}
          onCommit={(raw) => {
            const n = parseInt(raw, 10);
            if (!isNaN(n)) update(grade, level, Math.max(1, Math.min(MAX_LEVEL, n)));
          }}
          placeholder="—"
        />
        {' ' + t('sections.erg.levelLabel') + ')'}
      </div>
    </div>
  );
};

const ErgSection = ({ lines, erg_grade, erg_level, erg_max_level, onLineChange }) => {
  return (
    <div className="space-y-2">
      <ErgGradeRow
        grade={erg_grade ?? null}
        level={erg_level ?? null}
        maxLevel={erg_max_level ?? null}
        hasLines={lines?.length > 0}
        onLineChange={onLineChange}
      />
    </div>
  );
};

export default ErgSection;
