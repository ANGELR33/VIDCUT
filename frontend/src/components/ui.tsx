import { useState, type ReactNode } from "react";
import { cn } from "@/utils/cn";

/* Sección expandible/ocultable con cabecera limpia */
export function Collapsible({
  title,
  right,
  defaultOpen = true,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  right?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={cn("border-b border-white/[0.06] last:border-b-0", className)}>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="group flex min-w-0 flex-1 items-center gap-2 py-2.5 text-left"
        >
          <svg
            viewBox="0 0 24 24"
            className={cn(
              "h-3 w-3 shrink-0 text-white/35 transition-transform duration-200 group-hover:text-beam-300",
              open ? "rotate-90" : "rotate-0",
            )}
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M9 6l6 6-6 6" />
          </svg>
          <span className="text-[11.5px] font-medium tracking-normal truncate text-white/70 group-hover:text-white transition-colors">
            {title}
          </span>
        </button>
        {right}
      </div>
      {open && <div className={cn("pb-3", bodyClassName)}>{children}</div>}
    </section>
  );
}

export function Panel({
  children,
  className,
  tone = "glass",
}: {
  children: ReactNode;
  className?: string;
  tone?: "glass" | "soft" | "deep";
}) {
  return (
    <div
      className={cn(
        tone === "glass" && "glass",
        tone === "soft" && "glass-soft",
        tone === "deep" && "glass-deep",
        "rounded-2xl",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionLabel({
  children,
  right,
  className,
}: {
  children: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-3 px-1", className)}>
      <span className="micro text-white/35">{children}</span>
      {right}
    </div>
  );
}

export function IconButton({
  children,
  onClick,
  active,
  title,
  className,
  size = "md",
}: {
  children: ReactNode;
  onClick?: () => void;
  active?: boolean;
  title?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className={cn(
        "group relative grid place-items-center rounded-xl border transition-all duration-300",
        size === "sm" && "h-7 w-7",
        size === "md" && "h-9 w-9",
        size === "lg" && "h-11 w-11",
        active
          ? "border-beam-400/60 bg-beam-500/15 text-beam-200"
          : "border-white/[0.09] bg-black text-white/50 hover:border-beam-400/40 hover:text-white",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Toggle({
  on,
  onChange,
  label,
  hint,
}: {
  on: boolean;
  onChange: () => void;
  label: string;
  hint?: string;
}) {
  return (
    <button
      onClick={onChange}
      className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.03]"
    >
      <span className="min-w-0">
        <span className="block text-[11px] leading-tight text-white/70">{label}</span>
        {hint && <span className="micro-sm mt-1 block text-white/25">{hint}</span>}
      </span>
      <span
        className={cn(
          "relative h-[14px] w-[26px] shrink-0 rounded-full border transition-all duration-300",
          on
            ? "border-beam-400/60 bg-beam-500/30"
            : "border-white/10 bg-black",
        )}
      >
        <span
          className={cn(
            "absolute top-[1.5px] h-[9px] w-[9px] rounded-full transition-all duration-300",
            on ? "left-[14px] bg-beam-200" : "left-[2px] bg-white/35",
          )}
        />
      </span>
    </button>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: { id: T; label: string; glyph?: string }[];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-0.5 rounded-lg border border-white/[0.08] bg-black p-0.5",
        className,
      )}
    >
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={cn(
            "relative flex-1 rounded-md px-2 py-[5px] text-[10px] font-medium tracking-wide transition-colors duration-200",
            value === o.id
              ? "bg-beam-500 text-white"
              : "text-white/35 hover:text-white/65",
          )}
        >
          {o.glyph && <span className="mr-1 opacity-60">{o.glyph}</span>}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Meter({
  value,
  tone = "beam",
  height = 3,
}: {
  value: number;
  tone?: "beam" | "signal" | "ember";
  height?: number;
}) {
  const grad = tone === "beam" ? "#2f5cff" : tone === "signal" ? "#46e0c0" : "#ff7a59";
  return (
    <div
      className="w-full overflow-hidden rounded-full bg-white/[0.05]"
      style={{ height }}
    >
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: grad }}
      />
    </div>
  );
}

export function Stat({
  label,
  value,
  unit,
  delta,
  glyph,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  glyph?: ReactNode;
}) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-white/[0.08] bg-black p-2.5 transition-colors hover:border-beam-400/40">
      <div className="flex items-center justify-between">
        <span className="micro-sm text-white/30">{label}</span>
        {glyph && <span className="text-white/20">{glyph}</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="tnum text-[17px] font-light leading-none text-white">{value}</span>
        {unit && <span className="text-[10px] text-white/35">{unit}</span>}
      </div>
      {delta && (
        <div className="mt-1.5 text-[9.5px] font-medium tracking-wide text-signal-400">
          {delta}
        </div>
      )}
    </div>
  );
}

export function Hairline({ className }: { className?: string }) {
  return <div className={cn("hairline h-px w-full opacity-60", className)} />;
}

export function Glyph({ children, tone = "beam" }: { children: ReactNode; tone?: "beam" | "signal" }) {
  return (
    <span
      className={cn(
        "grid h-6 w-6 shrink-0 place-items-center rounded-lg border text-[11px] leading-none",
        tone === "beam"
          ? "border-beam-400/25 bg-beam-500/10 text-beam-200"
          : "border-signal-400/25 bg-signal-400/10 text-signal-400",
      )}
    >
      {children}
    </span>
  );
}
