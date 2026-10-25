import { useState } from "react";
import { login, register } from "../lib/api.js";

// Sign-in / create-account modal. Calls onAuthed({token, user}) on success.
export default function AuthDialog({ onAuthed, onClose }) {
  const [tab, setTab] = useState("login"); // login | register
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const fn = tab === "login" ? login : register;
      onAuthed(await fn(username.trim(), password));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="card modal" onSubmit={submit}>
        <div className="segmented" role="tablist">
          {[
            ["login", "Sign in"],
            ["register", "Create account"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={tab === key ? "active" : ""}
              onClick={() => {
                setTab(key);
                setError("");
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <label className="field-label" htmlFor="auth-user">Username</label>
        <input
          id="auth-user"
          className="text-input"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
          required
          minLength={3}
          maxLength={32}
          pattern="[A-Za-z0-9_.\-]+"
          title="3–32 characters: letters, numbers, _ . -"
        />

        <label className="field-label" htmlFor="auth-pass">Password</label>
        <input
          id="auth-pass"
          className="text-input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={tab === "login" ? "current-password" : "new-password"}
          required
          minLength={8}
          maxLength={72}
        />
        {tab === "register" && <p className="hint small">At least 8 characters.</p>}

        {error && <p className="error">{error}</p>}

        <div className="modal-actions">
          <button type="button" className="ghost-btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-btn" disabled={busy}>
            {busy ? "Please wait…" : tab === "login" ? "Sign in" : "Create account"}
          </button>
        </div>
      </form>
    </div>
  );
}
