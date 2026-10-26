import { useEffect } from "react";
import { AUTOMATIONS } from "@/lib/data";
import { EditorProvider, useEditor } from "@/lib/store";
import { LeftPanel } from "@/components/LeftPanel";
import { MetricsPanel, ActivityBar } from "@/components/MetricsPanel";
import { PreviewStage, Transport } from "@/components/PreviewStage";
import { Timeline } from "@/components/Timeline";
import { TopBar } from "@/components/TopBar";
import { KeyboardShortcutsModal } from "@/components/KeyboardShortcutsModal";
import { ImportModal } from "@/components/ImportModal";
import { SilenceModal } from "@/components/SilenceModal";
import { cn } from "@/utils/cn";

/* chips de IA para pantallas sin panel izquierdo */
function CompactAI() {
  const { run, applied, progress } = useEditor();
  return (
    <div className="flex shrink-0 items-center gap-2 overflow-x-auto px-3 py-2 md:hidden">
      {AUTOMATIONS.slice(0, 5).map((a) => {
        const p = progress[a.id];
        const done = applied.includes(a.id);
        return (
          <button
            key={a.id}
            onClick={() => run(a.id)}
            disabled={done || p !== undefined}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] transition-all",
              done
                ? "border-signal-400/25 bg-signal-400/[0.07] text-signal-400/80"
                : p !== undefined
                  ? "border-beam-400/40 bg-beam-500/15 text-beam-100"
                  : "border-white/[0.08] bg-white/[0.02] text-white/60",
            )}
          >
            <span>{a.glyph}</span>
            {done ? "Aplicado" : p !== undefined ? `${Math.round(p)}%` : a.name}
          </button>
        );
      })}
    </div>
  );
}

function Shell() {
  const {
    mobileMenuOpen,
    setMobileMenuOpen,
    shortcutsModalOpen,
    setShortcutsModalOpen,
    importModalOpen,
    setImportModalOpen,
    silenceModalOpen,
    setSilenceModalOpen,
    theaterMode,
    setTheaterMode,
  } = useEditor();

  // Atajo de teclado para salir de Modo Cine con tecla Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && theaterMode) {
        setTheaterMode(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [theaterMode, setTheaterMode]);

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-ink-1000 text-white">
      {/* fondo negro sólido */}
      <div className="pointer-events-none fixed inset-0 -z-10 bg-black" />

      <TopBar />

      <main className="flex min-h-0 flex-1 relative overflow-hidden">
        {/* Panel Izquierdo: Oculto en Modo Cine para dar 100% de protagonismo al editor */}
        <div className={cn("h-full min-h-0 hidden md:flex shrink-0 transition-all duration-300", theaterMode && "!hidden")}>
          <LeftPanel />
        </div>

        {/* Editor Central: Vista previa y Línea de tiempo son los protagonistas absolutos */}
        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <PreviewStage />
          <CompactAI />
          <Transport />
          <Timeline />
        </div>

        {/* Panel Derecho: Oculto en Modo Cine */}
        <div className={cn("h-full min-h-0 flex shrink-0 transition-all duration-300", theaterMode && "!hidden")}>
          <MetricsPanel />
        </div>
      </main>

      {/* Mobile Drawer (LeftPanel con Proyectos, Generador IA, Nichos Virales, Subtítulos) */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden animate-in fade-in duration-200">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-md"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative z-10 flex h-full w-[90vw] max-w-[340px] flex-col bg-ink-950/98 border-r border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.9)] backdrop-blur-2xl animate-in slide-in-from-left duration-250">
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08] shrink-0">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-beam-400 anim-ping" />
                <span className="text-[12px] font-semibold uppercase tracking-wider text-white">
                  Menú del Estudio
                </span>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="grid h-7 w-7 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-white/60 hover:text-white"
                title="Cerrar menú"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0">
              <LeftPanel />
            </div>
          </div>
        </div>
      )}

      {/* Modales de herramientas profesionales */}
      <KeyboardShortcutsModal
        isOpen={shortcutsModalOpen}
        onClose={() => setShortcutsModalOpen(false)}
      />
      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
      />
      <SilenceModal
        isOpen={silenceModalOpen}
        onClose={() => setSilenceModalOpen(false)}
      />

      <ActivityBar />
    </div>
  );
}

export default function App() {
  return (
    <EditorProvider>
      <Shell />
    </EditorProvider>
  );
}
