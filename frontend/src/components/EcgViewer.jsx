import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/**
 * A full-screen look at one recording.
 *
 * <p>The rendered ECG is 2800 by 1800 pixels at exactly ten pixels per
 * millimetre, which is what makes a measurement off the image meaningful. Shown
 * in a 240-pixel card it is scaled to about an eighth of that, and a reviewer
 * verifying a PR interval cannot see the P-wave onset at all.
 *
 * <p>So the zoom levels are expressed in millimetres rather than as arbitrary
 * multiples. At "actual size" one millimetre on screen is ten pixels, the same
 * as the render, which is the level at which the small squares are countable --
 * and counting small squares is how the measurement is actually taken.
 */

/** The render's own scale: 10 px per mm, so 1 small square (1 mm) is 10 px. */
const PIXELS_PER_MM = 10;

const ZOOM_STEPS = [1, 1.5, 2, 3, 4, 6];
const MIN_ZOOM = ZOOM_STEPS[0];
const MAX_ZOOM = ZOOM_STEPS[ZOOM_STEPS.length - 1];

export default function EcgViewer({ url, caseId, label, onClose }) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const dragging = useRef(null);
  const frameRef = useRef(null);

  const reset = useCallback(() => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  const step = useCallback((direction) => {
    setZoom((current) => {
      const next = direction > 0
        ? ZOOM_STEPS.find((value) => value > current + 0.01)
        : [...ZOOM_STEPS].reverse().find((value) => value < current - 0.01);
      return next ?? current;
    });
  }, []);

  // Escape closes, plus the zoom keys a reader reaches for without thinking.
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
      else if (event.key === "+" || event.key === "=") step(1);
      else if (event.key === "-" || event.key === "_") step(-1);
      else if (event.key === "0") reset();
    };
    window.addEventListener("keydown", onKey);
    // The page behind must not scroll while this is open.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, step, reset]);

  const onWheel = (event) => {
    event.preventDefault();
    setZoom((current) => {
      const next = current * (event.deltaY < 0 ? 1.15 : 1 / 1.15);
      return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
    });
  };

  const onPointerDown = (event) => {
    dragging.current = { x: event.clientX - offset.x, y: event.clientY - offset.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event) => {
    if (!dragging.current) return;
    setOffset({ x: event.clientX - dragging.current.x, y: event.clientY - dragging.current.y });
  };

  const onPointerUp = (event) => {
    dragging.current = null;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  // How wide one small square is on this screen, at this zoom. A reviewer
  // counting squares wants to know whether what they are looking at is bigger
  // or smaller than the paper it came from.
  const mmOnScreen = (PIXELS_PER_MM * zoom).toFixed(1);

  // Rendered into document.body rather than in place. A fixed-position element
  // is contained by any ancestor carrying a transform, and the card this opens
  // from has one for its hover lift -- so in place, "full screen" was the size
  // of the card.
  return createPortal(
    <div
      className="fixed inset-0 z-50 bg-[#05070f] flex flex-col"
      role="dialog"
      aria-modal="true"
      aria-label={label || `ECG for case ${caseId}`}
    >
      <div className="flex items-center gap-3 px-4 py-3 text-sm text-white/80 border-b border-white/10">
        <span className="font-semibold">{label || `Case ${caseId}`}</span>
        <span className="text-white/40 text-xs">
          {zoom === 1 ? "fit to width" : `${zoom.toFixed(1)}×`} · 1 mm ≈ {mmOnScreen} px
        </span>

        <span className="ml-auto flex items-center gap-2">
          <button onClick={() => step(-1)} disabled={zoom <= MIN_ZOOM}
                  className="px-3 py-1 rounded border border-white/20 disabled:opacity-30" title="Zoom out (−)">
            −
          </button>
          <button onClick={() => step(1)} disabled={zoom >= MAX_ZOOM}
                  className="px-3 py-1 rounded border border-white/20 disabled:opacity-30" title="Zoom in (+)">
            +
          </button>
          <button onClick={reset} className="px-3 py-1 rounded border border-white/20 text-xs" title="Reset (0)">
            Reset
          </button>
          <button onClick={onClose} className="px-3 py-1 rounded border border-white/20 text-xs" title="Close (Esc)">
            Close
          </button>
        </span>
      </div>

      <div
        ref={frameRef}
        className="flex-1 overflow-hidden bg-white"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ cursor: zoom > 1 ? "grab" : "default", touchAction: "none" }}
      >
        <img
          src={url}
          alt={`12-lead ECG for case ${caseId}`}
          draggable={false}
          className="select-none origin-top-left"
          style={{
            // At zoom 1 the image fits the width; above that it grows from the
            // same corner so panning stays predictable.
            width: `${zoom * 100}%`,
            // Without this the width above does nothing: the global stylesheet
            // sets max-width 100% on every image, so a zoomed image is clamped
            // straight back to the container and the zoom silently has no effect.
            maxWidth: "none",
            transform: `translate(${offset.x}px, ${offset.y}px)`,
          }}
        />
      </div>

      <p className="px-4 py-2 text-[11px] text-white/40">
        Scroll or use + and − to zoom, drag to move, Esc to close. Rendered at 25 mm/s and
        10 mm/mV, so one large square is 0.2 s and 0.5 mV.
      </p>
    </div>,
    document.body,
  );
}
