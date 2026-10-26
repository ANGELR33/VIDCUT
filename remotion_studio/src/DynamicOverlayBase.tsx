import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type DynamicOverlayProps = {
  durationSec: number;
  width: number;
  height: number;
  fps: number;
  vertical: boolean;
  theme?: {
    primary?: string;
    accent?: string;
    bg?: string;
    textColor?: string;
  };
  data?: Record<string, any>;
};

/**
 * Plantilla base / contenedor dinámico para componentes Remotion generados por IA.
 * Proporciona helpers de animación estándar con spring y transiciones elásticas.
 */
export const DynamicOverlayContainer: React.FC<
  DynamicOverlayProps & { children: React.ReactNode }
> = ({ children, durationSec, fps }) => {
  const frame = useCurrentFrame();
  const totalFrames = Math.max(1, Math.round(durationSec * fps));

  // Entrada con spring elástico (primeros 12 frames)
  const enterSpring = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 180, mass: 0.8 },
    durationInFrames: 15,
  });

  // Salida suave en los últimos 10 frames
  const exitProgress = interpolate(
    frame,
    [totalFrames - 10, totalFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = Math.min(1, enterSpring * 1.2) * exitProgress;
  const scale = interpolate(enterSpring, [0, 1], [0.92, 1.0]);

  return (
    <AbsoluteFill
      style={{
        opacity,
        transform: `scale(${scale})`,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
