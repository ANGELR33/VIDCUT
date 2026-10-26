import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { DynamicOverlayContainer, DynamicOverlayProps } from "./DynamicOverlayBase";

export type MetricCounterProps = DynamicOverlayProps & {
  title?: string;
  fromValue?: number;
  toValue?: number;
  suffix?: string;
  prefix?: string;
  subtitle?: string;
};

/**
 * Componente Remotion React: Contador dinámico con animación spring de micro-física,
 * resplandor neón adaptativo y estética Glassmorphism estilo Bloomberg/Vox.
 */
export const MetricCounter: React.FC<MetricCounterProps> = (props) => {
  const {
    title = "INCREMENTO DETECTADO",
    fromValue = 0,
    toValue = 250,
    suffix = "%",
    prefix = "+",
    subtitle = "DATO VERIFICADO EN TIEMPO REAL",
    theme = {},
  } = props;

  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();

  const primaryColor = theme.primary || "#38BDF8"; // Cyan divulgador
  const accentColor = theme.accent || "#FFE14D";   // Amarillo vibrante

  // Resorte para conteo numérico progresivo
  const countProgress = spring({
    frame: Math.max(0, frame - 5),
    fps,
    config: { damping: 18, stiffness: 90, mass: 1.0 },
    durationInFrames: 35,
  });

  const currentValue = Math.round(
    interpolate(countProgress, [0, 1], [fromValue, toValue])
  );

  const glowPulse = interpolate(
    Math.sin(frame / 6),
    [-1, 1],
    [0.7, 1.0]
  );

  return (
    <DynamicOverlayContainer {...props}>
      <div
        style={{
          background: "rgba(10, 14, 26, 0.78)",
          backdropFilter: "blur(16px)",
          border: `1.5px solid ${primaryColor}66`,
          borderRadius: 24,
          padding: "24px 42px",
          boxShadow: `0 20px 50px rgba(0,0,0,0.6), 0 0 30px ${primaryColor}33`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 12,
          fontFamily: '"Montserrat", "Segoe UI", sans-serif',
          maxWidth: width * 0.85,
        }}
      >
        {/* Título Badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 16,
            fontWeight: 800,
            letterSpacing: "0.15em",
            color: accentColor,
            textTransform: "uppercase",
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: accentColor,
              boxShadow: `0 0 10px ${accentColor}`,
            }}
          />
          {title}
        </div>

        {/* Número Gigante */}
        <div
          style={{
            fontSize: 68,
            fontWeight: 900,
            color: "#FFFFFF",
            letterSpacing: "-0.02em",
            textShadow: `0 0 ${25 * glowPulse}px ${primaryColor}`,
            display: "flex",
            alignItems: "baseline",
            lineHeight: 1,
          }}
        >
          <span style={{ color: primaryColor, marginRight: 4 }}>{prefix}</span>
          {currentValue.toLocaleString()}
          <span style={{ color: accentColor, fontSize: 44, marginLeft: 4 }}>
            {suffix}
          </span>
        </div>

        {/* Subtítulo aclaratorio */}
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "rgba(255, 255, 255, 0.7)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {subtitle}
        </div>
      </div>
    </DynamicOverlayContainer>
  );
};
