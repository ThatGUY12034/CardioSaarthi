import { useEffect, useRef } from "react";

export default function ECGWaveform({ imageUrl, height = 260, label }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (imageUrl) return; // use image if provided
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const { width, height: canvasHeight } = canvas;
    ctx.fillStyle = "#0a1128";
    ctx.fillRect(0, 0, width, canvasHeight);

    // Grid
    ctx.strokeStyle = "rgba(239, 68, 68, 0.15)";
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 12) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
    }
    for (let y = 0; y < canvasHeight; y += 12) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
    }

    // Fake waveform
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let x = 0; x < width; x++) {
      const t = x / 40;
      const y =
        canvasHeight / 2 +
        Math.sin(t) * 8 +
        Math.exp(-(Math.pow(((x % 120) - 60), 2) / 50)) * -40 +
        Math.exp(-(Math.pow(((x % 120) - 65), 2) / 20)) * 30;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }, [imageUrl]);

  if (imageUrl) {
    return (
      <div className="rounded-lg overflow-hidden border border-white/10">
        {label && <div className="bg-brand-cardLight px-3 py-2 text-xs text-brand-muted">{label}</div>}
        <img src={imageUrl} alt="ECG" className="w-full" style={{ height }} />
      </div>
    );
  }

  return (
    <div className="rounded-lg overflow-hidden border border-white/10">
      {label && <div className="bg-brand-cardLight px-3 py-2 text-xs text-brand-muted">{label}</div>}
      <canvas ref={canvasRef} width={800} height={height} className="w-full" />
    </div>
  );
}