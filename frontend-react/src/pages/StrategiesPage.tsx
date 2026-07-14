import { useState } from "react";
import { Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import {
  useCreateStrategyMutation,
  useDeleteStrategyMutation,
  useGetMLStrategiesQuery,
  useGetStopLossTypesQuery,
  useGetUserStrategiesQuery,
  useUpdateStrategyMutation,
} from "../store/api";
import type { Session, StrategyConfig } from "../types";

type StrategiesPageProps = {
  session: Session;
};

export function StrategiesPage({ session }: StrategiesPageProps) {
  const { data: strategies, isLoading, isError } = useGetUserStrategiesQuery(session.id);
  const [showModal, setShowModal] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<StrategyConfig | null>(null);

  const openCreate = () => {
    setEditingStrategy(null);
    setShowModal(true);
  };

  const openEdit = (strategy: StrategyConfig) => {
    setEditingStrategy(strategy);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingStrategy(null);
  };

  return (
    <section className="panel strategies-panel">
      <div className="table-header">
        <h2>My Strategies</h2>
        <button className="primary-button" onClick={openCreate}>
          <Plus size={18} />
          <span>Add Strategy</span>
        </button>
      </div>

      {isLoading && (
        <p className="panel-muted">
          <Loader2 size={16} className="spin" /> Loading strategies…
        </p>
      )}
      {isError && <p className="panel-muted">Could not load strategies.</p>}
      {strategies && strategies.length === 0 && (
        <p className="panel-muted">No strategies yet. Create your first one!</p>
      )}
      {strategies && strategies.length > 0 && (
        <table className="strategy-table-full">
          <thead>
            <tr>
              <th>Name</th>
              <th>Symbol</th>
              <th>Max Position</th>
              <th>Enabled</th>
              <th>ML</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.name}</strong></td>
                <td>{s.symbol}</td>
                <td>{s.maxPositionSize}</td>
                <td>{s.enabled ? "✅" : "❌"}</td>
                <td>{s.useML ? (s.mlStrategyDisplayName ?? "Yes") : "—"}</td>
                <td>
                  <div className="api-key-actions">
                    <button className="icon-button" onClick={() => openEdit(s)} title="Edit">
                      <Pencil size={16} />
                    </button>
                    <DeleteStrategyButton strategyId={s.id} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showModal && (
        <StrategyConfigModal
          session={session}
          strategy={editingStrategy}
          onClose={closeModal}
        />
      )}
    </section>
  );
}

function DeleteStrategyButton({ strategyId }: { strategyId: string }) {
  const [deleteStrategy, { isLoading }] = useDeleteStrategyMutation();
  return (
    <button
      className="icon-button danger"
      onClick={() => {
        if (window.confirm("Delete this strategy configuration?")) {
          deleteStrategy(strategyId);
        }
      }}
      disabled={isLoading}
      title="Delete"
    >
      {isLoading ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Modal                                                              */
/* ------------------------------------------------------------------ */

type ModalProps = {
  session: Session;
  strategy: StrategyConfig | null;
  onClose: () => void;
};

function StrategyConfigModal({ session, strategy, onClose }: ModalProps) {
  const isEdit = strategy !== null;

  const { data: stopLossTypes } = useGetStopLossTypesQuery();
  const { data: mlStrategies } = useGetMLStrategiesQuery();
  const [createStrategy, { isLoading: isCreating }] = useCreateStrategyMutation();
  const [updateStrategy, { isLoading: isUpdating }] = useUpdateStrategyMutation();

  const [name, setName] = useState(strategy?.name ?? "");
  const [symbol, setSymbol] = useState(strategy?.symbol ?? "");
  const [maxPositionSize, setMaxPositionSize] = useState(strategy?.maxPositionSize?.toString() ?? "");
  const [enabled, setEnabled] = useState(strategy?.enabled ?? false);

  // Risk
  const [maxDrawdown, setMaxDrawdown] = useState(strategy?.maxDrawdown?.toString() ?? "");
  const [maxRiskPerTrade, setMaxRiskPerTrade] = useState(strategy?.maxRiskPerTrade?.toString() ?? "");
  const [maxDailyLoss, setMaxDailyLoss] = useState(strategy?.maxDailyLoss?.toString() ?? "");
  const [maxOpenPositions, setMaxOpenPositions] = useState(strategy?.maxOpenPositions?.toString() ?? "");

  // Trade
  const [stopLossTypeId, setStopLossTypeId] = useState(strategy?.stopLossTypeId ?? "");
  const [stopLoss, setStopLoss] = useState(strategy?.stopLoss?.toString() ?? "");
  const [takeProfit, setTakeProfit] = useState(strategy?.takeProfit?.toString() ?? "");
  const [spreadThreshold, setSpreadThreshold] = useState(strategy?.spreadThreshold?.toString() ?? "");

  // Time
  const [tradingWindowStart, setTradingWindowStart] = useState(strategy?.tradingWindowStart ?? "");
  const [tradingWindowEnd, setTradingWindowEnd] = useState(strategy?.tradingWindowEnd ?? "");
  const [trailingStopActivation, setTrailingStopActivation] = useState(strategy?.trailingStopActivation?.toString() ?? "");
  const [breakEvenTrigger, setBreakEvenTrigger] = useState(strategy?.breakEvenTrigger?.toString() ?? "");

  // ML
  const [useML, setUseML] = useState(strategy?.useML ?? false);
  const [mlStrategyId, setMlStrategyId] = useState(strategy?.mlStrategyId ?? "");

  const [error, setError] = useState<string | null>(null);

  const toNumOrNull = (val: string): number | null => {
    const trimmed = val.trim();
    if (trimmed === "") return null;
    const n = Number(trimmed);
    return isNaN(n) ? null : n;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim() || !symbol.trim() || !maxPositionSize.trim()) {
      setError("Name, symbol, and max position size are required.");
      return;
    }

    const body = {
      name: name.trim(),
      symbol: symbol.trim(),
      maxPositionSize: Number(maxPositionSize),
      enabled,
      maxDrawdown: toNumOrNull(maxDrawdown),
      maxRiskPerTrade: toNumOrNull(maxRiskPerTrade),
      maxDailyLoss: toNumOrNull(maxDailyLoss),
      maxOpenPositions: toNumOrNull(maxOpenPositions),
      stopLossTypeId: stopLossTypeId || null,
      stopLoss: toNumOrNull(stopLoss),
      takeProfit: toNumOrNull(takeProfit),
      spreadThreshold: toNumOrNull(spreadThreshold),
      tradingWindowStart: tradingWindowStart || null,
      tradingWindowEnd: tradingWindowEnd || null,
      trailingStopActivation: toNumOrNull(trailingStopActivation),
      breakEvenTrigger: toNumOrNull(breakEvenTrigger),
      useML,
      mlStrategyId: useML ? (mlStrategyId || null) : null,
    };

    try {
      if (isEdit && strategy) {
        await updateStrategy({ id: strategy.id, body }).unwrap();
      } else {
        await createStrategy({ ...body, userId: session.id } as any).unwrap();
      }
      onClose();
    } catch (err: any) {
      setError(err?.data?.message ?? "Failed to save strategy.");
    }
  };

  const isLoading = isCreating || isUpdating;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{isEdit ? "Edit Strategy" : "Add Strategy"}</h2>
          <button className="icon-button" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <form className="strategy-form" onSubmit={handleSubmit}>
          {error && <p className="form-error">{error}</p>}

          {/* General */}
          <fieldset>
            <legend>General</legend>
            <div className="form-row">
              <label>
                <span>Name *</span>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Momentum BTC" />
              </label>
              <label>
                <span>Symbol *</span>
                <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="e.g. BTCUSDT" />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span>Max Position Size *</span>
                <input type="number" step="0.01" value={maxPositionSize} onChange={(e) => setMaxPositionSize(e.target.value)} />
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
                <span>Enabled</span>
              </label>
            </div>
          </fieldset>

          {/* Risk Management */}
          <fieldset>
            <legend>Risk Management</legend>
            <div className="form-row">
              <label>
                <span>Max Drawdown (%)</span>
                <input type="number" step="0.01" value={maxDrawdown} onChange={(e) => setMaxDrawdown(e.target.value)} />
              </label>
              <label>
                <span>Max Risk Per Trade (%)</span>
                <input type="number" step="0.01" value={maxRiskPerTrade} onChange={(e) => setMaxRiskPerTrade(e.target.value)} />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span>Max Daily Loss (%)</span>
                <input type="number" step="0.01" value={maxDailyLoss} onChange={(e) => setMaxDailyLoss(e.target.value)} />
              </label>
              <label>
                <span>Max Open Positions</span>
                <input type="number" step="1" value={maxOpenPositions} onChange={(e) => setMaxOpenPositions(e.target.value)} />
              </label>
            </div>
          </fieldset>

          {/* Trade Parameters */}
          <fieldset>
            <legend>Trade Parameters</legend>
            <div className="form-row">
              <label>
                <span>Stop Loss Type</span>
                <select value={stopLossTypeId} onChange={(e) => setStopLossTypeId(e.target.value)}>
                  <option value="">— None —</option>
                  {stopLossTypes?.map((t) => (
                    <option key={t.id} value={t.id}>{t.displayName}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Stop Loss (%)</span>
                <input type="number" step="0.01" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span>Take Profit (%)</span>
                <input type="number" step="0.01" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} />
              </label>
              <label>
                <span>Spread Threshold</span>
                <input type="number" step="0.0001" value={spreadThreshold} onChange={(e) => setSpreadThreshold(e.target.value)} />
              </label>
            </div>
          </fieldset>

          {/* Time & Execution */}
          <fieldset>
            <legend>Time & Execution</legend>
            <div className="form-row">
              <label>
                <span>Trading Window Start</span>
                <input type="time" value={tradingWindowStart} onChange={(e) => setTradingWindowStart(e.target.value)} />
              </label>
              <label>
                <span>Trading Window End</span>
                <input type="time" value={tradingWindowEnd} onChange={(e) => setTradingWindowEnd(e.target.value)} />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span>Trailing Stop Activation (%)</span>
                <input type="number" step="0.01" value={trailingStopActivation} onChange={(e) => setTrailingStopActivation(e.target.value)} />
              </label>
              <label>
                <span>Break Even Trigger (%)</span>
                <input type="number" step="0.01" value={breakEvenTrigger} onChange={(e) => setBreakEvenTrigger(e.target.value)} />
              </label>
            </div>
          </fieldset>

          {/* ML Strategy */}
          <fieldset>
            <legend>Machine Learning</legend>
            <label className="checkbox-label">
              <input type="checkbox" checked={useML} onChange={(e) => setUseML(e.target.checked)} />
              <span>Implement ML Strategies</span>
            </label>
            {useML && (
              <label>
                <span>ML Strategy</span>
                <select value={mlStrategyId} onChange={(e) => setMlStrategyId(e.target.value)}>
                  <option value="">— Select —</option>
                  {mlStrategies?.map((m) => (
                    <option key={m.id} value={m.id}>{m.displayName}</option>
                  ))}
                </select>
                {mlStrategies && mlStrategies.length === 0 && (
                  <p className="field-hint">No ML strategies available yet. Add them in the database when ready.</p>
                )}
              </label>
            )}
          </fieldset>

          <div className="form-actions">
            <button type="button" className="ghost-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={isLoading}>
              {isLoading ? <><Loader2 size={16} className="spin" /> Saving…</> : isEdit ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}