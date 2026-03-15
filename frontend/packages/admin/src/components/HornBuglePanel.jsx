import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { getHornBugleHistory } from '@mabi/shared/api/hornBugle';
import PlayerName from '@mabi/shared/components/PlayerName';

const container = 'max-w-3xl mx-auto p-6';
const messageRow = 'flex gap-3 py-2 border-b border-gray-700/50 text-sm';
const nameCol = 'shrink-0 w-32 font-bold truncate';
const messageCol = 'flex-1 text-gray-300';
const timeCol = 'shrink-0 text-xs text-gray-500 self-center';

const SERVER = '류트';

const formatTime = (dateStr) => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
};

const HornBugle = () => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const { data } = await getHornBugleHistory(SERVER);
      setMessages(data.horn_bugle_world_history || []);
    } catch (e) {
      console.error('Failed to fetch horn bugle history:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className={container}>
      <h1 className="text-2xl font-bold text-cyan-400 mb-6">
        {t('hornBugle.title', '뿔피리')}
        <span className="text-sm text-gray-500 ml-2">{SERVER}</span>
      </h1>

      {loading ? (
        <p className="text-gray-500">{t('common.loading', 'Loading...')}</p>
      ) : messages.length === 0 ? (
        <p className="text-gray-500">{t('hornBugle.empty', 'No messages')}</p>
      ) : (
        <div>
          {messages.map((msg, i) => (
            <div key={i} className={messageRow}>
              <div className={nameCol}>
                <PlayerName gameId={msg.character_name} />
              </div>
              <div className={messageCol}>{msg.message}</div>
              <div className={timeCol}>{formatTime(msg.date_send)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default HornBugle;
