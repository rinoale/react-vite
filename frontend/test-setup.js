import '@testing-library/jest-dom';

// Mock i18next — returns the translation key as-is
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
    i18n: { changeLanguage: vi.fn() },
  }),
}));

// Default empty game config globals
window.GAME_ITEMS_CONFIG = [];
window.ENCHANTS_CONFIG = [];
window.REFORGES_CONFIG = [];
