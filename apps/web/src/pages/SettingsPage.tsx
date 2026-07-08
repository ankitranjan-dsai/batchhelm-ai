import { useState } from "react";
import { KeyRound, Save, Trash2, ShieldCheck } from "lucide-react";
import { getDemoKey, setDemoKey, clearDemoKey } from "../auth";
import { PanelHeader } from "./shared";

export function SettingsPage() {
  const [demoKey, setDemoKeyState] = useState(getDemoKey());
  const [saved, setSaved] = useState(false);

  function handleSave(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = demoKey.trim();
    if (trimmed) {
      setDemoKey(trimmed);
    } else {
      clearDemoKey();
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleClear() {
    clearDemoKey();
    setDemoKeyState("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="page-content">
      <PanelHeader title="Settings" subtitle="Configure access and preferences" />

      <section className="panel settings-panel">
        <div className="settings-intro">
          <ShieldCheck size={24} aria-hidden="true" />
          <div>
            <h2>Demo Access Key</h2>
            <p>
              If the backend requires a demo key, enter it here. It is stored only in
              your browser session and sent as the{" "}
              <code>X-BatchHelm-Demo-Key</code> header on API requests.
            </p>
          </div>
        </div>

        <form className="settings-form" onSubmit={handleSave}>
          <label htmlFor="demo-key" className="sr-only">
            Demo access key
          </label>
          <div className="settings-input-row">
            <KeyRound size={18} aria-hidden="true" />
            <input
              id="demo-key"
              type="password"
              value={demoKey}
              onChange={(event) => setDemoKeyState(event.currentTarget.value)}
              placeholder="Enter demo access key"
              autoComplete="off"
            />
          </div>
          <div className="settings-actions">
            <button type="submit" className="primary-button">
              <Save size={16} />
              Save key
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={handleClear}
              disabled={!demoKey}
            >
              <Trash2 size={16} />
              Clear key
            </button>
          </div>
          {saved ? (
            <p className="settings-saved" role="status">
              Demo key saved.
            </p>
          ) : null}
        </form>
      </section>
    </div>
  );
}
