import React from 'react';
import { getLevelBadge } from '../styles';

/**
 * Level badge with color tier based on level vs max.
 * Drop-in replacement for `<span className={getLevelBadge(...)}>`.
 */
const LevelBadge = ({ level, maxLevel, minLevel, className = '', children, ...rest }) => {
  const badge = getLevelBadge(level, maxLevel, minLevel);
  return (
    <span className={`${badge} ${className}`} {...rest}>
      {children}
    </span>
  );
};

export default LevelBadge;
