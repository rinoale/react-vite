import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Play, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getJobs, triggerJob, getJobHistory } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  loadingCenter, loadingIcon, dividerY, metaRow, hoverRow,
  jobRow, jobName, jobDesc, jobMeta, jobMetaResult, jobMetaError, badgeCyan,
  iconSmSpin, iconSm, btnJobRun, btnPagGray, thRow, thCell, tdCell, tdCellMono, tdCellSub, tdCellTrunc,
} from '@mabi/shared/styles';

const statusConfig = {
  completed: { icon: CheckCircle, color: 'text-emerald-400' },
  failed: { icon: XCircle, color: 'text-red-400' },
  running: { icon: Loader2, color: 'text-cyan-400 animate-spin' },
  pending: { icon: Clock, color: 'text-yellow-400' },
};

const StatusIcon = ({ status }) => {
  const cfg = statusConfig[status] || statusConfig.pending;
  const Icon = cfg.icon;
  return <Icon className={`w-4 h-4 ${cfg.color}`} />;
};

const formatTime = (iso) => {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
};

const formatInterval = (seconds) => {
  if (!seconds) return null;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
};

const JobsPanel = () => {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState([]);
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [runningJobs, setRunningJobs] = useState({});
  const [expandedRow, setExpandedRow] = useState(null);
  const [historyPagination, setHistoryPagination] = useState({ limit: 20, offset: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [jobsRes, historyRes] = await Promise.all([
        getJobs(),
        getJobHistory({ limit: historyPagination.limit, offset: historyPagination.offset }),
      ]);
      setJobs(jobsRes.data);
      setHistory(historyRes.data.rows || []);
    } catch (err) {
      console.error('Error fetching jobs:', err);
    } finally {
      setIsLoading(false);
    }
  }, [historyPagination.offset, historyPagination.limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleTrigger = useCallback(async (name) => {
    setRunningJobs((prev) => ({ ...prev, [name]: true }));
    try {
      await triggerJob(name);
      setTimeout(fetchData, 1500);
    } catch (err) {
      console.error('Error triggering job:', err);
    } finally {
      setRunningJobs((prev) => ({ ...prev, [name]: false }));
    }
  }, [fetchData]);

  if (isLoading && jobs.length === 0) {
    return (
      <div className={loadingCenter}>
        <Loader2 className={loadingIcon} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* job-list */}
      <div className={panelOuter}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>{t('jobs.title')}</h2>
          <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('jobs.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className={dividerY}>
          {jobs.map((job) => {
            const lastRun = job.last_run;
            return (
              <div key={job.name} className={jobRow}>
                <div className="flex-1">
                  <div className={metaRow}>
                    <p className={jobName}>{job.name}</p>
                    {job.schedule_seconds && (
                      <span className={badgeCyan}>{t('jobs.every', { interval: formatInterval(job.schedule_seconds) })}</span>
                    )}
                  </div>
                  <p className={jobDesc}>{job.description}</p>
                  {lastRun && (
                    <div className={metaRow}>
                      <StatusIcon status={lastRun.status} />
                      <span className={jobMeta}>{formatTime(lastRun.started_at)}</span>
                      {lastRun.result_summary && (
                        <span className={jobMetaResult}>{lastRun.result_summary}</span>
                      )}
                      {lastRun.error && (
                        <span className={jobMetaError}>{lastRun.error}</span>
                      )}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleTrigger(job.name)}
                  disabled={runningJobs[job.name]}
                  className={btnJobRun}
                >
                  {runningJobs[job.name]
                    ? <Loader2 className={iconSmSpin} />
                    : <Play className={iconSm} />}
                  {t('jobs.run')}
                </button>
              </div>
            );
          })}
          {jobs.length === 0 && (
            <div className={panelEmpty}>{t('jobs.noJobs')}</div>
          )}
        </div>
      </div>

      {/* job-history */}
      <div className={panelOuter}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>{t('jobs.history')}</h2>
          <div className={metaRow}>
            <button
              onClick={() => setHistoryPagination((p) => ({ ...p, offset: Math.max(0, p.offset - p.limit) }))}
              className={btnPagGray}
              disabled={historyPagination.offset === 0}
            >
              {t('jobs.prev')}
            </button>
            <button
              onClick={() => setHistoryPagination((p) => ({ ...p, offset: p.offset + p.limit }))}
              className={btnPagGray}
              disabled={history.length < historyPagination.limit}
            >
              {t('jobs.next')}
            </button>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className={thRow}>
              <th className={thCell}>{t('jobs.colStatus')}</th>
              <th className={thCell}>{t('jobs.colName')}</th>
              <th className={thCell}>{t('jobs.colWorker')}</th>
              <th className={thCell}>{t('jobs.colPayload')}</th>
              <th className={thCell}>{t('jobs.colStarted')}</th>
              <th className={thCell}>{t('jobs.colFinished')}</th>
              <th className={thCell}>{t('jobs.colResult')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {history.map((run) => (
              <React.Fragment key={run.id}>
                <tr className={`${hoverRow} cursor-pointer`} onClick={() => setExpandedRow(expandedRow === run.id ? null : run.id)}>
                  <td className={tdCell}><StatusIcon status={run.status} /></td>
                  <td className={tdCellMono}>{run.job_name}</td>
                  <td className={tdCellSub}>{run.worker_id || '-'}</td>
                  <td className={tdCellTrunc}>{run.payload || '-'}</td>
                  <td className={tdCellSub}>{formatTime(run.started_at)}</td>
                  <td className={tdCellSub}>{formatTime(run.finished_at)}</td>
                  <td className={tdCellTrunc}>
                    {run.error ? <span className="text-red-400">{run.error}</span> : (run.result_summary || '-')}
                  </td>
                </tr>
                {expandedRow === run.id && (
                  <tr>
                    <td colSpan={7} className="px-4 py-3 bg-gray-800/50">
                      <div className="space-y-1 text-xs font-mono text-gray-300 break-all whitespace-pre-wrap">
                        {run.payload && <div><span className="text-gray-500">payload: </span>{run.payload}</div>}
                        {run.result_summary && <div><span className="text-gray-500">result: </span>{run.result_summary}</div>}
                        {run.error && <div><span className="text-gray-500">error: </span><span className="text-red-400">{run.error}</span></div>}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {history.length === 0 && (
              <tr>
                <td colSpan={7} className={panelEmpty}>{t('jobs.noHistory')}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default JobsPanel;
