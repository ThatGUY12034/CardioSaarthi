import { useEffect, useState } from "react";
import { getRemarks, markRemarkRead } from "../api/studyApi";

/**
 * What a teacher said, and about which attempt.
 *
 * <p>Unread first, because a remark the student has not seen is the only one
 * that can still change what they do next. Opening one marks it read; nothing
 * else about it can change, which is what makes it a record of the conversation
 * rather than of whatever it was last edited to.
 */
export default function RemarksPanel({ limit = 10 }) {
  const [remarks, setRemarks] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getRemarks(limit)
      .then((data) => {
        if (!cancelled) setRemarks(data);
      })
      .catch(() => {
        // A failure here must not take the page down with it: remarks are
        // context, and the student's own progress is the point of the page.
        if (!cancelled) setRemarks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [limit]);

  const show = async (remark) => {
    setOpen(open === remark.id ? null : remark.id);
    if (!remark.readAt) {
      try {
        await markRemarkRead(remark.id);
        setRemarks((current) =>
          current.map((r) => (r.id === remark.id ? { ...r, readAt: new Date().toISOString() } : r))
        );
      } catch {
        // Marking read is a convenience. Failing to record it should not stop
        // the student reading the thing.
      }
    }
  };

  if (remarks === null || remarks.length === 0) {
    return null;
  }

  const unread = remarks.filter((r) => !r.readAt).length;

  return (
    <div className="card p-6 mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-semibold">From your faculty</h2>
        {unread > 0 && (
          <span className="text-xs px-2 py-1 rounded-full bg-brand-primary/20 text-brand-accent">
            {unread} unread
          </span>
        )}
      </div>
      <p className="text-xs text-brand-muted mt-1">
        Left on a specific answer you gave.
      </p>

      <ul className="mt-4 space-y-2">
        {remarks.map((r) => (
          <li
            key={r.id}
            className={`rounded-lg border ${
              r.readAt ? "border-white/5" : "border-brand-primary/40 bg-brand-primary/5"
            }`}
          >
            <button
              onClick={() => show(r)}
              aria-expanded={open === r.id}
              className="w-full text-left px-4 py-3"
            >
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <span className="text-sm font-medium">
                  {r.stepLabel}
                  <span className="text-brand-muted font-normal">
                    {" "}
                    · recording {r.sourceEcgId}
                  </span>
                </span>
                <span className="text-[11px] text-brand-muted">
                  {r.reviewerName}
                  {!r.readAt && <span className="text-brand-accent ml-2">new</span>}
                </span>
              </div>
            </button>
            {open === r.id && (
              <p className="px-4 pb-4 text-sm leading-relaxed text-brand-muted">{r.body}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
