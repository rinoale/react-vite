import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const TYPE_STYLES = {
  success: 'bg-green-950/80 border-green-700 text-green-300',
  error: 'bg-red-950/80 border-red-700 text-red-300',
  warning: 'bg-yellow-950/80 border-yellow-700 text-yellow-300',
  info: 'bg-blue-950/80 border-blue-700 text-blue-300',
};

const TYPE_ICONS = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

export default function Toast({ id, type = 'info', message, duration = 4000, onClose }) {
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  const handleClose = useCallback(() => {
    setExiting(true);
    setTimeout(() => onClose(id), 300);
  }, [id, onClose]);

  useEffect(() => {
    // Trigger enter animation on next frame
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (duration <= 0) return;
    const timer = setTimeout(() => handleClose(), duration);
    return () => clearTimeout(timer);
  }, [duration, handleClose]);

  const Icon = TYPE_ICONS[type] || Info;

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg backdrop-blur-sm max-w-sm w-full transition-all duration-300 ease-out ${TYPE_STYLES[type] || TYPE_STYLES.info} ${visible && !exiting ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}`}
      role="alert"
    >
      <Icon className="w-5 h-5 shrink-0 mt-0.5" />
      <p className="text-sm font-medium flex-1">{message}</p>
      <button
        onClick={handleClose}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Close"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
