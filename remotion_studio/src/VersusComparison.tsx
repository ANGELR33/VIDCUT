import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DynamicOverlayContainer, DynamicOverlayProps } from "./DynamicOverlayBase";

export type VersusComparisonProps = DynamicOverlayProps & {
  tagA?: string;
  labelA?: string;
  tagB?: string;
  labelB?: string;
  category?: string;
};

/**
 * Componente Remotion React: Comparativa Versus / Split dinámico con choque cinemático.
 */
export const VersusComparison: React.FC<VersusComparisonProps> = (props) => {
  const {
    tagA = "ANTES",
    labelA = "MÉTODO TRADICIONAL",
    tagB = "AHORA",
    labelB = "REVOLUCIÓN CON IA",
    category = "COMPARATIVA DE IMPACTO",
    theme = {},
  } = props;

  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const colorA = theme.primary || "#F43F5E"; // Carmesí / Rose
  const colorB = theme.accent || "#10B981";  // Verde esmeralda

  // Entrada desde los costados
  const slideInA = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 140, mass: 0.8 },
  });

  const slideInB = spring({
    frame: Math.max(0, frame - 4),
    fps,
    config: { damping: 15, stiffness: 140, mass: 0.8 },
  });

  const vsPop = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: { damping: 10, stiffness: 220, mass: 0.6 },
  });

  return (
    <DynamicOverlayContainer {...props}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
          fontFamily: '"Montserrat", "Segoe UI", sans-serif',
        }}
      >
        <div
          style={{
            fontSize: 13,
            fontWeight: 800,
            letterSpacing: "0.2em",
            color: "rgba(255, 255, 255, 0.7)",
            background: "rgba(0,0,0,0.5)",
            padding: "4px 14px",
            borderRadius: 999,
            border: "1px solid rgba(255,255,255,0.15)",
          }}
        >
          {category}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
          }}
        >
          {/* Lado A */}
          <div
            style={{
              transform: `translateX(${interpolate(slideInA, [0, 1], [-80, 0])}px)`,
              opacity: slideInA,
              background: "rgba(15, 23, 42, 0.85)",
              border: `2px solid ${colorA}`,
              borderRadius: 20,
              padding: "20px 28px",
              minWidth: 220,
              textAlign: "center",
              boxShadow: `0 10px 30px ${colorA}33`,
            }}
          >
            <div style={{ color: colorA, fontSize: 13, fontWeight: 900, letterSpacing: "0.1em" }}>
              {tagA}
            </div>
            <div style={{ color: "#FFF", fontSize: 22, fontWeight: 800, marginTop: 4 }}>
              {labelA}
            </div>
          </div>

          {/* Insignia Central VS */}
          <div
            style={{
              transform: `scale(${vsPop})`,
              background: "#0F172A",
              border: "2px solid #FFF",
              borderRadius: "50%",
              width: 48,
              height: 48,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 900,
              fontSize: 18,
              color: "#FFF",
              boxShadow: "0 0 20px rgba(255,255,255,0.4)",
              zIndex: 2,
            }}
          >
            VS
          </div>

          {/* Lado B */}
          <div
            style={{
              transform: `translateX(${interpolate(slideInB, [0, 1], [80, 0])}px)`,
              opacity: slideInB,
              background: "rgba(15, 23, 42, 0.85)",
              border: `2px solid ${colorB}`,
              borderRadius: 20,
              padding: "20px 28px",
              minWidth: 220,
              textAlign: "center",
              boxShadow: `0 10px 30px ${colorB}33`,
            }}
          >
            <div style={{ color: colorB, fontSize: 13, fontWeight: 900, letterSpacing: "0.1em" }}>
              {tagB}
            </div>
            <div style={{ color: "#FFF", fontSize: 22, fontWeight: 800, marginTop: 4 }}>
              {labelB}
            </div>
          </div>
        </div>
      </div>
    </DynamicOverlayContainer>
  );
};
