import { AlertTriangle, Lock } from "lucide-react";
import { useState } from "react";
import { getDemoKey, setDemoKey } from "./auth";

interface AuthGateProps {
  children: React.ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const [key, setKey] = useState(getDemoKey());
  const [input, setInput] = useState("");
  const [error, setError] = useState("");

  if (key) {
    return <>{children}</>;
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) {
      setError("Please enter the demo access key.");
      return;
    }
    setDemoKey(trimmed);
    setKey(trimmed);
    setError("");
  }

  return (
    <div className="auth-gate">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-icon">
          <Lock size={28} />
        </div>
        <h1>BatchHelm AI</h1>
        <p>Enter the demo access key to open the recall command center.</p>
        <input
          type="password"
          placeholder="Demo access key"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          autoFocus
        />
        {error ? (
          <div className="auth-error" role="alert">
            <AlertTriangle size={16} />
            {error}
          </div>
        ) : null}
        <button type="submit">Enter command center</button>
      </form>
    </div>
  );
}
