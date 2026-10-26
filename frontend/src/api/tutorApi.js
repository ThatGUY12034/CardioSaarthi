import axiosClient from "./axiosClient";

/**
 * The tutor, and the queue of material that decides what it may say.
 *
 * <p>Every answer carries citations. An answer with none is a refusal, and the
 * refusal is the designed behaviour rather than a failure: retrieval finding
 * nothing means no approved source covers the question, and answering anyway
 * would be the one thing this platform exists not to do.
 */

/** Ask a question. Returns `{ text, citations, refused, concept }`. */
export async function askTutor(question, concept = null, sessionId = null) {
  const { data } = await axiosClient.post("/study/tutor/ask", {
    question,
    concept,
    sessionId,
  });
  return data;
}

/** Background reading for one of the nine steps. */
export async function getConceptReading(concept) {
  const { data } = await axiosClient.get(`/study/tutor/concept/${concept}`);
  return data;
}

// ---------------------------------------------------------------------------
// faculty
// ---------------------------------------------------------------------------
/** Paragraphs awaiting a decision. */
export async function getKnowledgeQueue(status = "pending", concept = null, limit = 25) {
  const { data } = await axiosClient.get("/knowledge/queue", {
    params: { status, concept, limit },
  });
  return data;
}

/** How full the library is, and how much of it a person actually read. */
export async function getKnowledgeStatus() {
  const { data } = await axiosClient.get("/knowledge/status");
  return data;
}

/**
 * Approve or reject one paragraph. There is no edit: the text is quoted
 * material under a licence requiring attribution, and a database trigger
 * refuses any change to it.
 */
export async function reviewChunk(id, action, reason = null) {
  const { data } = await axiosClient.post(`/knowledge/${id}/review`, { action, reason });
  return data;
}
