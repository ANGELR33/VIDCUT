import { useEffect } from "react";
import { IconClose } from "./Icons";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

const SHORTCUT_GROUPS = [
  {
    category: "Reproducción & Transporte",
    items: [
      { keys: ["Espacio"], description: "Reproducir / Pausar video" },
      { keys: ["J"], description: "Rebobinar 5 segundos" },
      { keys: ["K"], description: "Pausar reproducción" },
      { keys: ["L"], description: "Avanzar 5 segundos" },
      { keys: ["Home"], description: "Ir al inicio del timeline" },
      { keys: ["End"], description: "Ir al final del timeline" },
    ],
  },
  {
    category: "Edición & Cortes",
    items: [
      { keys: ["S"], description: "Dividir clip en el cabezal (Split)" },
      { keys: ["C"], description: "Dividir clip alternativo" },
      { keys: ["Supr", "Backspace"], description: "Eliminar clip seleccionado" },
      { keys: ["I"], description: "Marcar punto de entrada (In)" },
      { keys: ["O"], description: "Marcar punto de salida (Out)" },
    ],
  },
  {
    category: "Interfaz & Vistas",
    items: [
      { keys: ["Ctrl", "B"], description: "Expandir u ocultar menú lateral" },
      { keys: ["?"], description: "Abrir o cerrar esta guía de atajos" },
      { keys: ["Esc"], description: "Cerrar modales y deseleccionar" },
    ],
  },
];

export function KeyboardShortcutsModal({ isOpen, onClose }: Props) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 transition-all duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-white/10 bg-[#080808] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.9)] animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-white/80 text-[13px] font-mono">
              ⌨
            </span>
            <div>
              <h3 className="text-[14px] font-semibold text-white tracking-tight">
                Atajos de Teclado Profesionales
              </h3>
              <p className="text-[11px] text-white/40">
                Edita a velocidad de estudio sin tocar el ratón
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

        {/* Content */}
        <div className="mt-5 space-y-5 max-h-[60vh] overflow-y-auto pr-1 subtle-scrollbar">
          {SHORTCUT_GROUPS.map((grp) => (
            <div key={grp.category} className="space-y-2.5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-white/40">
                {grp.category}
              </span>
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] divide-y divide-white/[0.04] overflow-hidden">
                {grp.items.map((it, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.02] transition-colors"
                  >
                    <span className="text-[11.5px] text-white/80">
                      {it.description}
                    </span>
                    <div className="flex items-center gap-1">
                      {it.keys.map((k, kIdx) => (
                        <kbd
                          key={kIdx}
                          className="rounded-md border border-white/15 bg-white/[0.06] px-2 py-0.5 text-[10px] font-mono font-medium text-white shadow-sm"
                        >
                          {k}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-between pt-4 border-t border-white/[0.08] text-[11px] text-white/40">
          <span>Pulsa <kbd className="font-mono text-white/70">?</kbd> en cualquier momento para ver esta guía</span>
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-xl border border-white/15 bg-white/[0.08] hover:bg-white/[0.14] text-white text-[11px] font-medium transition-all cursor-pointer"
          >
            Entendido
          </button>
        </div>
      </div>
    </div>
  );
}
