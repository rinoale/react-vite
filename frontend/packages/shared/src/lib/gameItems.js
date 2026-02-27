/** Game item config helpers — thin wrappers over window.GAME_ITEMS_CONFIG */

export const getGameItemsConfig = () => window.GAME_ITEMS_CONFIG || [];

export const findGameItemByName = (name) =>
  getGameItemsConfig().find(gi => gi.name === name);

export const searchGameItemsLocal = (q, limit = 20) => {
  const lower = q.toLowerCase();
  return getGameItemsConfig()
    .filter(gi => gi.name.toLowerCase().includes(lower))
    .slice(0, limit);
};
