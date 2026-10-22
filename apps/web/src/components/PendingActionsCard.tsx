import React, { useState, useEffect } from 'react';
import { PendingAction } from '../types';
import { ShieldAlert, CheckCircle, XCircle, Clock, Send, Trash2, Edit3 } from 'lucide-react';

interface PendingActionsCardProps {
  action: PendingAction;
  onActionResolved?: () => void;
}

export const PendingActionsCard: React.FC<PendingActionsCardProps> = ({
  action,
  onActionResolved,
}) => {
  const [status, setStatus] = useState<string>(action.status);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [timeLeft, setTimeLeft] = useState<string>('');

  useEffect(() => {
    const updateCountdown = () => {
      const expires = new Date(action.expires_at).getTime();
      const now = new Date().getTime();
      const diffSec = Math.max(0, Math.floor((expires - now) / 1000));

      if (diffSec === 0) {
        setTimeLeft('Expired');
        if (status === 'pending') setStatus('expired');
      } else {
        const mins = Math.floor(diffSec / 60);
        const secs = diffSec % 60;
        setTimeLeft(`${mins}m ${secs < 10 ? '0' : ''}${secs}s`);
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [action.expires_at, status]);

  const handleConfirm = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`/api/actions/${action.token}/confirm`, {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok) {
        setStatus('confirmed');
        setFeedback(data.message || 'Action executed successfully in simulated sandbox.');
        if (onActionResolved) onActionResolved();
      } else {
        setFeedback(`Error: ${data.detail || 'Failed to confirm'}`);
      }
    } catch (err: any) {
      setFeedback(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`/api/actions/${action.token}/reject`, {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok) {
        setStatus('rejected');
        setFeedback(data.message || 'Action safely rejected and cancelled.');
        if (onActionResolved) onActionResolved();
      } else {
        setFeedback(`Error: ${data.detail || 'Failed to reject'}`);
      }
    } catch (err: any) {
      setFeedback(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = () => {
    if (action.action_type.includes('email')) return <Send className="w-4 h-4 text-amber-400" />;
    if (action.action_type.includes('delete')) return <Trash2 className="w-4 h-4 text-rose-400" />;
    if (action.action_type.includes('edit')) return <Edit3 className="w-4 h-4 text-blue-400" />;
    return <ShieldAlert className="w-4 h-4 text-amber-400" />;
  };

  return (
    <div className="bg-slate-900 border border-amber-500/30 rounded-xl p-4 shadow-lg shadow-amber-950/20 text-xs space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          {getActionIcon()}
          <span className="font-semibold text-slate-200 uppercase tracking-wide">
            Pending Human Approval
          </span>
        </div>
        <div className="flex items-center gap-1 text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-500/20">
          <Clock className="w-3 h-3" />
          <span>{timeLeft}</span>
        </div>
      </div>

      <div>
        <p className="text-slate-200 font-medium text-sm leading-snug">{action.summary}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            Target: {action.target_system.toUpperCase()}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
            Token: {action.token}
          </span>
        </div>
      </div>

      {feedback && (
        <div
          className={`p-2.5 rounded-lg border text-xs ${
            status === 'confirmed'
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : status === 'rejected'
              ? 'bg-rose-950/40 border-rose-500/30 text-rose-300'
              : 'bg-slate-800 border-slate-700 text-slate-300'
          }`}
        >
          {feedback}
        </div>
      )}

      {status === 'pending' && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={handleConfirm}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition disabled:opacity-50"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Confirm & Execute</span>
          </button>
          <button
            onClick={handleReject}
            disabled={loading}
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 bg-rose-600/80 hover:bg-rose-600 text-white font-medium rounded-lg transition disabled:opacity-50"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Reject Action</span>
          </button>
        </div>
      )}

      {status !== 'pending' && (
        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400 pt-1">
          <span className="capitalize">Status:</span>
          <span
            className={`font-semibold capitalize ${
              status === 'confirmed'
                ? 'text-emerald-400'
                : status === 'rejected'
                ? 'text-rose-400'
                : 'text-slate-500'
            }`}
          >
            {status}
          </span>
        </div>
      )}
    </div>
  );
};
