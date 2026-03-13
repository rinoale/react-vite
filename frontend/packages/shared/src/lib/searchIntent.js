let _intent = null;

export const setSearchIntent = (q, by = 'id') => { _intent = { q, by }; };
export const consumeSearchIntent = () => { const v = _intent; _intent = null; return v; };
