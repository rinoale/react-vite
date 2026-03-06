const SERVER_COLORS = {
  '류트': 'text-blue-400',
  '만돌린': 'text-orange-400',
  '하프': 'text-pink-400',
  '울프': 'text-gray-400',
};

const gameIdColor = (name) => {
  if (!name) return '#9ca3af';
  const c = [0, 0, 0];
  for (let i = 0; i < name.length; i++) c[i % 3] += name.charCodeAt(i);
  return '#' + c.map(v => ((v * 101) % 97 + 159).toString(16).toUpperCase()).join('');
};

const PlayerName = ({ server, gameId, className = 'text-xs' }) => {
  if (!server && !gameId) return null;
  return (
    <span className={className}>
      {server && (
        <span className={`font-bold ${SERVER_COLORS[server] || 'text-gray-400'}`}>{server}</span>
      )}
      {server && gameId && ' / '}
      {gameId && (
        <span style={{ color: gameIdColor(gameId) }}>{gameId}</span>
      )}
    </span>
  );
};

export default PlayerName;
