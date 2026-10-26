import React from "react";
import { Composition } from "remotion";
import { KaiCaptions, KaiCaptionsProps } from "./KaiCaptions";
import { MetricCounter, MetricCounterProps } from "./MetricCounter";
import { VersusComparison, VersusComparisonProps } from "./VersusComparison";

const defaultCaptionsProps: KaiCaptionsProps = {
  words: [
    { text: "Esto", start: 0.2, end: 0.5 },
    { text: "cambia", start: 0.5, end: 0.9 },
    { text: "todo", start: 0.9, end: 1.3, emphasis: true },
    { text: "lo", start: 1.4, end: 1.6 },
    { text: "que", start: 1.6, end: 1.8 },
    { text: "sabíamos.", start: 1.8, end: 2.6 },
  ],
  durationSec: 3,
  width: 1920,
  height: 300,
  fps: 30,
  vertical: false,
  activeColor: "#FFE14D",
  emphasisColor: "#38BDF8",
};

const defaultMetricProps: MetricCounterProps = {
  durationSec: 3.5,
  width: 1920,
  height: 1080,
  fps: 30,
  vertical: false,
  title: "CRECIMIENTO ACELERADO",
  fromValue: 0,
  toValue: 340,
  suffix: "%",
  prefix: "+",
  subtitle: "MÉTRICA REGISTRADA POR IA",
  theme: {
    primary: "#38BDF8",
    accent: "#FFE14D",
  },
};

const defaultVersusProps: VersusComparisonProps = {
  durationSec: 3.5,
  width: 1920,
  height: 1080,
  fps: 30,
  vertical: false,
  tagA: "MÉTODO ANTIGUO",
  labelA: "LENTO Y MANUAL",
  tagB: "NUEVO ESTÁNDAR",
  labelB: "AUTOMATIZADO AL 100%",
  category: "ANÁLISIS ESTRATÉGICO",
  theme: {
    primary: "#F43F5E",
    accent: "#10B981",
  },
};

export const Root: React.FC = () => (
  <>
    {/* Subtítulos dinámicos estilo Kai */}
    <Composition
      id="KaiCaptions"
      component={KaiCaptions}
      width={defaultCaptionsProps.width}
      height={defaultCaptionsProps.height}
      fps={defaultCaptionsProps.fps}
      durationInFrames={Math.round(defaultCaptionsProps.durationSec * defaultCaptionsProps.fps)}
      defaultProps={defaultCaptionsProps}
      calculateMetadata={({ props }) => ({
        width: props.width,
        height: props.height,
        fps: props.fps,
        durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)),
      })}
    />

    {/* Contador de Impacto Numérico Animado */}
    <Composition
      id="MetricCounter"
      component={MetricCounter}
      width={defaultMetricProps.width}
      height={defaultMetricProps.height}
      fps={defaultMetricProps.fps}
      durationInFrames={Math.round(defaultMetricProps.durationSec * defaultMetricProps.fps)}
      defaultProps={defaultMetricProps}
      calculateMetadata={({ props }) => ({
        width: props.width,
        height: props.height,
        fps: props.fps,
        durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)),
      })}
    />

    {/* Comparativa Versus / Split Animada */}
    <Composition
      id="VersusComparison"
      component={VersusComparison}
      width={defaultVersusProps.width}
      height={defaultVersusProps.height}
      fps={defaultVersusProps.fps}
      durationInFrames={Math.round(defaultVersusProps.durationSec * defaultVersusProps.fps)}
      defaultProps={defaultVersusProps}
      calculateMetadata={({ props }) => ({
        width: props.width,
        height: props.height,
        fps: props.fps,
        durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)),
      })}
    />
  </>
);
