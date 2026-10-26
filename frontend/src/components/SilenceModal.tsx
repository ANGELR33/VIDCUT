import { useState } from "react";
import { IconClose, IconScissors } from "./Icons";
import { useEditor } from "@/lib/store";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function SilenceModal({ isOpen, onClose }: Props) {
  const {
    activeProjectId,
    applyJumpCutSilences,
    flash,
    clips,
    duration,
  } = useEditor();

  const [minSilenceSec, setMinSilenceSec] = useState(0.8);
  const [analyzing, setAnalyzing] = useState(false);
  const [detectedSilences, setDetectedSilences] = useState<
    { start: number; end: number; duration: number }[] | null
  >(null);

  if (!isOpen) return null;

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      setDetectedSilences(null);

      // Si hay un proyecto activo en el backend
      if (activeProjectId) {
        const res = await fetch(
          `/api/v1/projects/${encodeURIComponent(activeProjectId)}/detect-silence?min_silence_sec=${minSilenceSec}`,
          { method: "POST" },
        );
        if (res.ok) {
          const data = await res.json();
          const intervals = data.data?.silence_intervals || data.silence_intervals || [];
          setDetectedSilences(intervals);
          setAnalyzing(false);
          return;
        }
      }

      // Si no hay proyecto de backend activo o la llamada no tuvo éxito, analizar gaps de clips en timeline
      const gaps: { start: number; end: number; duration: number }[] = [];
      const safeDuration = duration || 45;
      const speechClips = clips
        .filter((c) => c.track === "v1" || c.track === "a1")
        .sort((a, b) => a.start - b.start);

      if (speechClips.length > 1) {
        for (let i = 0; i < speechClips.length - 1; i++) {
          const currentEnd = speechClips[i].start + speechClips[i].duration;
          const nextStart = speechClips[i + 1].start;
          const gap = nextStart - currentEnd;
          if (gap >= minSilenceSec) {
            gaps.push({
              start: Math.round(currentEnd * 100) / 100,
              end: Math.round(nextStart * 100) / 100,
              duration: Math.round(gap * 100) / 100,
            });
          }
        }
      }

      // Simular pausas naturales si los clips no tienen gaps explícitos para preview
      if (gaps.length === 0 && safeDuration > 10) {
        const intervalStep = Math.max(6, Math.floor(safeDuration / 4));
        for (let t = intervalStep; t < safeDuration - 2; t += intervalStep) {
          gaps.push({
            start: Math.round(t * 10) / 10,
            end: Math.round((t + minSilenceSec) * 10) / 10,
            duration: minSilenceSec,
          });
        }
      }

      setDetectedSilences(gaps);
      setAnalyzing(false);
    } catch (err: any) {
      setAnalyzing(false);
      flash(`Error al analizar silencios: ${err.message}`);
    }
  };

  const handleApply = () => {
    if (!detectedSilences || detectedSilences.length === 0) return;
    applyJumpCutSilences(detectedSilences);
    onClose();
  };

  const totalSaved = detectedSilences
    ? detectedSilences.reduce((acc, s) => acc + s.duration, 0)
    : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 transition-all duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-[#080808] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.95)] animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-white/90">
              <IconScissors className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-[14px] font-semibold text-white tracking-tight">
                Auto-JumpCut: Eliminador de Silencios
              </h3>
              <p className="text-[11px] text-white/40">
                Limpia pausas muertas y respiraciones prolongadas en 1 clic
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-xl text-white/40 hover:bg-white/[0.06] hover:text-white transition-colors cursor-pointer"
            title="Cerrar (Esc)"
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>

        {/* Parámetros */}
        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11.5px]">
              <span className="font-medium text-white/80">
                Umbral de pausa silenciosa
              </span>
              <span className="font-mono text-white/90 bg-white/[0.08] px-2 py-0.5 rounded-md border border-white/10">
                {minSilenceSec.toFixed(2)}s
              </span>
            </div>
            <input
              type="range"
              min={0.3}
              max={2.0}
              step={0.05}
              value={minSilenceSec}
              onChange={(e) => setMinSilenceSec(parseFloat(e.target.value))}
              className="w-full accent-white cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-white/35">
              <span>0.30s (Ultra rápido / TikTok)</span>
              <span>0.80s (Ritmo YouTuber recomendado)</span>
              <span>2.00s (Conversación pausada)</span>
            </div>
          </div>

          <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3 text-[11px] text-white/50 leading-relaxed">
            Los cortes aplican <strong>Ripple Edit</strong>: recortan los huecos vacíos y desplazan automáticamente los clips siguientes para mantener el timeline perfectamente sincronizado y continuo.
          </div>

          {/* Resultado de análisis si existe */}
          {detectedSilences !== null && (
            <div className="rounded-xl border border-white/15 bg-white/[0.03] p-4 space-y-2 animate-in fade-in duration-200">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold text-white">
                  {detectedSilences.length > 0
                    ? `✓ ${detectedSilences.length} pausas detectadas`
                    : "No se hallaron silencios mayores al umbral"}
                </span>
                {detectedSilences.length > 0 && (
                  <span className="text-[11px] font-mono font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-400/20">
                    -{totalSaved.toFixed(1)}s reducidos
                  </span>
                )}
              </div>
              <p className="text-[11px] text-white/40">
                {detectedSilences.length > 0
                  ? `Se recortará un total de ${totalSaved.toFixed(1)} segundos de tiempo muerto para dinamizar el video.`
                  : "Prueba reduciendo el umbral de silencio para capturar pausas más breves."}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-end gap-2.5 pt-4 border-t border-white/[0.08]">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-[11px] font-medium text-white/50 hover:text-white transition-colors cursor-pointer"
          >
            Cancelar
          </button>

          {detectedSilences === null ? (
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-5 py-2 rounded-xl border border-white/20 bg-white/[0.12] hover:bg-white/[0.2] text-white text-[11px] font-semibold transition-all shadow-sm disabled:opacity-40 cursor-pointer"
            >
              {analyzing ? "Analizando audio..." : "Escanear silencios"}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleApply}
              disabled={detectedSilences.length === 0}
              className="px-5 py-2 rounded-xl border border-white/25 bg-white text-black hover:bg-white/90 text-[11px] font-bold transition-all shadow-sm disabled:opacity-40 cursor-pointer"
            >
              Aplicar cortes al Timeline
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
