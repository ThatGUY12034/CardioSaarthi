import { useEffect, useMemo, useState } from "react";
import Layout from "../../components/Layout";
import { EmptyState, ErrorState, InlineError, SkeletonRows } from "../../components/States";
import { getUsers, setActive } from "../../api/adminApi";
import { errorMessage } from "../../api/studyApi";

/**
 * Who has an account, across all three populations.
 *
 * <p>Access is revoked by deactivating, never by deleting. A reviewer's
 * decisions and a student's attempts are the evidence this platform is built to
 * preserve, and removing the person removes the attribution on all of it. A
 * deactivated account cannot authenticate from the next request onward, because
 * the principal lookup re-reads the flag every time rather than trusting a
 * token issued earlier.
 */

const KINDS = [
  ["", "Everyone"],
  ["reviewer", "Faculty & admins"],
  ["student", "Students"],
  ["patient", "Patients"],
];

const KIND_STYLE = {
  reviewer: "bg-brand-primary/20 text-brand-accent",
  student: "bg-brand-success/20 text-brand-success",
  patient: "bg-brand-warning/20 text-brand-warning",
};

export default function ManageUsers() {
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getUsers(kind || null)
      .then((data) => {
        if (!cancelled) setUsers(data);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load the account list."));
      });
    return () => {
      cancelled = true;
    };
  }, [kind, reloadKey]);

  const rows = useMemo(() => {
    if (!users) return null;
    const needle = query.trim().toLowerCase();
    if (!needle) return users;
    return users.filter(
      (u) =>
        u.fullName.toLowerCase().includes(needle) ||
        (u.email || "").toLowerCase().includes(needle) ||
        (u.identifier || "").toLowerCase().includes(needle)
    );
  }, [users, query]);

  const toggle = async (user) => {
    const key = `${user.kind}-${user.id}`;
    setBusyKey(key);
    setError(null);
    try {
      await setActive(user.kind, user.id, !user.active);
      setReloadKey((n) => n + 1);
    } catch (e) {
      setError(errorMessage(e, "That change was not saved."));
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <Layout role="ADMIN">
      <h1 className="page-title">Accounts</h1>
      <p className="page-subtitle">
        Faculty, students and patients. Access is revoked by deactivating, never by deleting.
      </p>

      {error && <div className="mt-6"><InlineError message={error} /></div>}

      <div className="flex flex-wrap items-center gap-3 mt-6">
        <div className="inline-flex rounded-lg bg-brand-card p-1 gap-1">
          {KINDS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setKind(value)}
              className={`px-3 py-2 rounded-md text-sm transition ${
                kind === value
                  ? "bg-brand-cardLight text-brand-text"
                  : "text-brand-muted hover:text-brand-text"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex-1 min-w-[200px]">
          <span className="sr-only">Search accounts</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name, email or ID…"
            className="w-full bg-brand-bg2 rounded-lg px-3 py-2 text-sm"
          />
        </label>
      </div>

      {rows === null ? (
        <SkeletonRows className="mt-6" count={5} />
      ) : rows.length === 0 ? (
        <EmptyState className="mt-6" title="No accounts match" description="Try a different filter or search." />
      ) : (
        <div className="card mt-6 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-brand-cardLight text-brand-muted text-xs uppercase">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">Name</th>
                  <th className="text-left px-5 py-3 font-medium">Type</th>
                  <th className="text-left px-5 py-3 font-medium">Identifier</th>
                  <th className="text-left px-5 py-3 font-medium">Email</th>
                  <th className="text-left px-5 py-3 font-medium">Status</th>
                  <th className="text-left px-5 py-3 font-medium">Access</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => {
                  const key = `${u.kind}-${u.id}`;
                  return (
                    <tr key={key} className="border-t border-white/5">
                      <td className="px-5 py-4 font-medium">{u.fullName}</td>
                      <td className="px-5 py-4">
                        <span className={`text-xs px-2 py-1 rounded ${KIND_STYLE[u.kind]}`}>
                          {u.role || u.kind}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-brand-muted">{u.identifier || "—"}</td>
                      <td className="px-5 py-4 text-brand-muted">{u.email}</td>
                      <td className="px-5 py-4">
                        {!u.canSignIn ? (
                          // An account with no password was invited and never
                          // taken up. That is not the same as being locked out.
                          <span className="text-xs text-brand-muted">invited</span>
                        ) : u.active ? (
                          <span className="text-xs text-brand-success">active</span>
                        ) : (
                          <span className="text-xs text-brand-danger">deactivated</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <button
                          onClick={() => toggle(u)}
                          disabled={busyKey === key}
                          className="btn-ghost text-xs !py-1.5 !px-3"
                        >
                          {u.active ? "Deactivate" : "Reactivate"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-brand-muted mt-4">
        Deactivation takes effect on the next request, not the next login: the server re-reads
        the flag every time rather than trusting a token issued earlier. New faculty and
        administrator accounts are created through the reviewer endpoint, which enforces a
        twelve-character minimum.
      </p>
    </Layout>
  );
}
