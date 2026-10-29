import { useContext } from "react";
import { RemarksContext } from "./remarksContext";

/**
 * How many remarks a student has not read, and how to say one was just read.
 *
 * <p>Safe to call anywhere. Outside a provider it reports zero rather than
 * throwing, which is what the non-student roles need.
 */
export function useUnreadRemarks() {
  return useContext(RemarksContext);
}
