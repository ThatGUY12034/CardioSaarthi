import { useCallback, useEffect, useMemo, useState } from "react";
import { RemarksContext } from "./remarksContext";
import { getUnreadRemarkCount } from "../api/studyApi";

/**
 * The unread count, held where both the navigation and the panel can reach it.
 *
 * <p>Two things render from the same number and neither owns it: the badge in
 * the sidebar, and the panel on the dashboard that marks a remark read when the
 * student opens it. Without shared state the badge would keep claiming a remark
 * was unread for as long as the student stayed on the page — the one moment it
 * is most obviously wrong, because they are looking at the thing they just
 * read.
 *
 * <p>Fetched only for students. The endpoint is scoped to the signed-in
 * student and a reviewer has no student row, so asking on their behalf would be
 * an error rather than a zero.
 */
export default function RemarksProvider({ role, children }) {
  const [unread, setUnread] = useState(0);

  const refresh = useCallback(() => {
    if (role !== "STUDENT") return;
    getUnreadRemarkCount()
      .then(setUnread)
      // A badge is not worth an error state. If the count cannot be read the
      // navigation simply shows none, and the remarks themselves are still on
      // the dashboard where they have always been.
      .catch(() => setUnread(0));
  }, [role]);

  useEffect(refresh, [refresh]);

  /**
   * One fewer, without a round trip.
   *
   * <p>The panel has already told the server. Re-fetching to learn what this
   * component could have worked out is a request whose answer is known, and it
   * would arrive after a visible pause.
   */
  const noteOneRead = useCallback(() => {
    setUnread((current) => Math.max(0, current - 1));
  }, []);

  const value = useMemo(
    () => ({ unread, noteOneRead, refresh }),
    [unread, noteOneRead, refresh]
  );

  return <RemarksContext.Provider value={value}>{children}</RemarksContext.Provider>;
}
