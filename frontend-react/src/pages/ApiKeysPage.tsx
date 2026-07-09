import { useState, type FormEvent } from "react";
import { Eye, EyeOff, Key, Loader2, Plus, Trash2 } from "lucide-react";
import {
  useCreateApiKeyMutation,
  useDeleteApiKeyMutation,
  useGetApiKeysQuery,
  useRevealApiKeyMutation,
} from "../store/api";
import type { Session } from "../types";

type ApiKeysPageProps = {
  session: Session;
};

export function ApiKeysPage({ session }: ApiKeysPageProps) {
  const { data: apiKeys, isLoading, isError } = useGetApiKeysQuery(session.id);
  const [createApiKey, { isLoading: isCreating }] = useCreateApiKeyMutation();
  const [revealApiKey] = useRevealApiKeyMutation();
  const [deleteApiKey] = useDeleteApiKeyMutation();

  const [label, setLabel] = useState("");
  const [broker, setBroker] = useState("etoro");
  const [publicKey, setPublicKey] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());
  const [revealedKeys, setRevealedKeys] = useState<Record<string, string>>({});
  const [revealingId, setRevealingId] = useState<string | null>(null);

  const handleCreate = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);

    if (!label.trim() || !publicKey.trim() || !privateKey.trim()) {
      setFormError("Label, public key and private key are required.");
      return;
    }

    try {
      await createApiKey({
        userId: session.id,
        label: label.trim(),
        broker: broker.trim(),
        publicKey: publicKey.trim(),
        privateKey: privateKey.trim(),
      }).unwrap();
      setLabel("");
      setPublicKey("");
      setPrivateKey("");
    } catch (err: any) {
      setFormError(err.data?.message || "Failed to create API key.");
    }
  };

  const handleReveal = async (id: string) => {
    if (revealedIds.has(id)) {
      // Already revealed — hide it
      setRevealedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      return;
    }

    setRevealingId(id);
    try {
      const result = await revealApiKey({ id, userId: session.id }).unwrap();
      const [pub, priv] = result.apiKey.split("|");
      setRevealedKeys((prev) => ({ ...prev, [id]: `Public: ${pub}\nPrivate: ${priv}` }));
      setRevealedIds((prev) => {
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      // Auto-hide after 30 seconds
      setTimeout(() => {
        setRevealedIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }, 30000);
    } catch {
      // ignore
    } finally {
      setRevealingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteApiKey({ id, userId: session.id }).unwrap();
    } catch {
      // ignore
    }
  };

  return (
    <section className="panel api-keys-panel">
      <div className="panel-header">
        <Key size={20} />
        <h2>API Keys Configuration</h2>
      </div>

      {/* User info */}
      <div className="api-keys-user-info">
        <span className="user-info-label">User:</span>
        <span className="user-info-value">{session.name}</span>
        <span className="user-info-separator">·</span>
        <span className="user-info-label">Email:</span>
        <span className="user-info-value">{session.email}</span>
      </div>

      {/* Create form */}
      <form className="api-key-form" onSubmit={handleCreate}>
        <div className="api-key-form-row">
          <label>
            <span>Label</span>
            <input
              required
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Etoro Main"
            />
          </label>
          <label>
            <span>Broker</span>
            <select value={broker} onChange={(e) => setBroker(e.target.value)}>
              <option value="etoro">eToro</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>
        <label>
          <span>Public Key</span>
          <input
            required
            value={publicKey}
            onChange={(e) => setPublicKey(e.target.value)}
            placeholder="Paste your public key here"
            type="password"
          />
        </label>
        <label>
          <span>Private Key</span>
          <input
            required
            value={privateKey}
            onChange={(e) => setPrivateKey(e.target.value)}
            placeholder="Paste your private key here"
            type="password"
          />
        </label>
        {formError && <p className="form-error">{formError}</p>}
        <button className="primary-button" type="submit" disabled={isCreating}>
          {isCreating ? <Loader2 size={18} className="spin" /> : <Plus size={18} />}
          <span>{isCreating ? "Saving…" : "Add API Key"}</span>
        </button>
      </form>

      {/* List */}
      <div className="api-keys-list">
        <h3>Saved API Keys</h3>
        {isLoading && (
          <p className="panel-muted">
            <Loader2 size={16} className="spin" /> Loading API keys…
          </p>
        )}
        {isError && <p className="panel-muted">Could not load API keys.</p>}
        {apiKeys && apiKeys.length === 0 && (
          <p className="panel-muted">No API keys configured yet.</p>
        )}
        {apiKeys && apiKeys.length > 0 && (
          <table className="api-key-table">
            <thead>
              <tr>
                <th>Label</th>
                <th>Broker</th>
                <th>Key</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((row) => (
                <tr key={row.id}>
                  <td>{row.label}</td>
                  <td>{row.broker}</td>
                  <td className="api-key-cell">
                    {revealedIds.has(row.id) ? (
                      <code className="revealed-key">{revealedKeys[row.id]}</code>
                    ) : (
                      <span className="masked-key">{row.maskedKey}</span>
                    )}
                  </td>
                  <td>{new Date(row.createdAt).toLocaleDateString()}</td>
                  <td className="api-key-actions">
                    <button
                      className="icon-button"
                      onClick={() => handleReveal(row.id)}
                      disabled={revealingId === row.id}
                      title={revealedIds.has(row.id) ? "Hide API key" : "Reveal API key"}
                    >
                      {revealingId === row.id ? (
                        <Loader2 size={16} className="spin" />
                      ) : revealedIds.has(row.id) ? (
                        <EyeOff size={16} />
                      ) : (
                        <Eye size={16} />
                      )}
                    </button>
                    <button
                      className="icon-button danger"
                      onClick={() => handleDelete(row.id)}
                      title="Delete API key"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}