import { createContext } from "react";

/**
 * The context object on its own, away from the component that provides it.
 *
 * <p>Split for the same reason the auth context is: React Fast Refresh can only
 * swap a module that exports components and nothing else, and a context object
 * replaced on every edit leaves the mounted tree holding the old one.
 *
 * <p>The default is a working value rather than null, because the sidebar is
 * rendered for faculty, patients and administrators too, and none of them has a
 * provider above them. A badge of zero is the correct answer for all three, so
 * there is nothing here to guard against and no reason for the hook to throw.
 */
export const RemarksContext = createContext({
  unread: 0,
  noteOneRead: () => {},
  refresh: () => {},
});
