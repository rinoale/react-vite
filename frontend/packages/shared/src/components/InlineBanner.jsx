import React, { useState } from 'react';
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

export default function InlineBanner({ type = 'info', message, onDismiss }) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const Icon = TYPE_ICONS[type] || Info;

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border w-full ${TYPE_STYLES[type] || TYPE_STYLES.info}`}
      role="alert"
    >
      <Icon className="w-5 h-5 shrink-0 mt-0.5" />
      <p className="text-sm font-medium flex-1">{message}</p>
      <button
        onClick={handleDismiss}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
