import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type CaptionWord = {
  text: string;
  start: number; // segundos desde el inicio de la escena
  end: number;
  emphasis?: boolean; // palabra clave: cifra, nombre propio, concepto fuerte
};

export type KaiCaptionsProps = {
  words: CaptionWord[];
  durationSec: number;
  width: number;
  height: number;
  fps: number;
  vertical: boolean;
  /** Color de la palabra que se está pronunciando. */
  activeColor: string;
  /** Color permanente de las palabras clave. */
  emphasisColor: string;
};

type Phrase = { words: CaptionWord[]; start: number; end: number };

const SENTENCE_END = /[.!?…]$/;
const SOFT_BREAK = /[,;:]$/;

/**
 * Agrupa palabras en frases cortas (estilo divulgador): rompe en puntuación,
 * pausas largas del locutor o al llegar al máximo de palabras/caracteres.
 */
export const buildPhrases = (
  words: CaptionWord[],
  maxWords: number,
  maxChars: number
): Phrase[] => {
  const phrases: Phrase[] = [];
  let current: CaptionWord[] = [];
  let chars = 0;

  const flush = () => {
    if (current.length) {
      phrases.push({
        words: current,
        start: current[0].start,
        end: current[current.length - 1].end,
      });
    }
    current = [];
    chars = 0;
  };

  words.forEach((w, i) => {
    const prev = current[current.length - 1];
    const gap = prev ? w.start - prev.end : 0;
    if (
      current.length &&
      (current.length >= maxWords ||
        chars + w.text.length + 1 > maxChars ||
        gap > 0.45)
    ) {
      flush();
    }
    current.push(w);
    chars += w.text.length + 1;
    const next = words[i + 1];
    const endsSentence = SENTENCE_END.test(w.text);
    const softBreak = SOFT_BREAK.test(w.text) && current.length >= 3;
    if (endsSentence || softBreak || !next) flush();
  });
  flush();
  return phrases;
};

const FONT_STACK =
  '"Montserrat", "Segoe UI Black", "Segoe UI", "Arial Black", Helvetica, Arial, sans-serif';

export const KaiCaptions: React.FC<KaiCaptionsProps> = ({
  words,
  vertical,
  activeColor,
  emphasisColor,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const maxWords = vertical ? 3 : 5;
  const maxChars = vertical ? 20 : 34;
  const phrases = React.useMemo(
    () => buildPhrases(words, maxWords, maxChars),
    [words, maxWords, maxChars]
  );

  // Frase visible: entra 50 ms antes de su primera palabra y se sostiene
  // 0.28 s tras la última (nunca solapa con la siguiente).
  let active: Phrase | undefined;
  let activeIdx = -1;
  phrases.forEach((p, i) => {
    const next = phrases[i + 1];
    const showFrom = p.start - 0.05;
    const hold = next ? Math.min(0.28, Math.max(0, next.start - 0.05 - p.end)) : 0.28;
    if (t >= showFrom && t < p.end + hold) {
      active = p;
      activeIdx = i;
    }
  });

  if (!active) return <AbsoluteFill />;

  const phrase: Phrase = active;
  const tIn = t - (phrase.start - 0.05);
  const next = phrases[activeIdx + 1];
  const hold = next ? Math.min(0.28, Math.max(0, next.start - 0.05 - phrase.end)) : 0.28;
  const tOut = phrase.end + hold - t;

  const enter = spring({
    frame: Math.max(0, Math.round(tIn * fps)),
    fps,
    config: { damping: 16, stiffness: 190, mass: 0.7 },
    durationInFrames: Math.round(0.32 * fps),
  });
  const exitFade = interpolate(tOut, [0, 0.12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const containerOpacity = Math.min(1, enter * 1.4) * exitFade;
  const containerY = interpolate(enter, [0, 1], [22, 0]);
  const containerScale = interpolate(enter, [0, 1], [0.94, 1]);

  const fontSize = vertical ? Math.round(width * 0.078) : Math.round(height * 0.235);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: vertical ? Math.round(height * 0.12) : Math.round(height * 0.12),
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "baseline",
          gap: `${Math.round(fontSize * 0.1)}px ${Math.round(fontSize * 0.4)}px`,
          maxWidth: vertical ? "92%" : "64%",
          padding: `${Math.round(fontSize * 0.22)}px ${Math.round(fontSize * 0.5)}px`,
          borderRadius: Math.round(fontSize * 0.5),
          background: "rgba(8, 10, 18, 0.62)",
          boxShadow: "0 10px 40px rgba(0,0,0,0.45), inset 0 0 0 1.5px rgba(255,255,255,0.10)",
          opacity: containerOpacity,
          transform: `translateY(${containerY}px) scale(${containerScale})`,
          fontFamily: FONT_STACK,
          fontWeight: 900,
          fontSize,
          lineHeight: 1.12,
          letterSpacing: "-0.01em",
          textAlign: "center",
        }}
      >
        {phrase.words.map((w, i) => {
          const spoken = t >= w.start;
          const speaking = t >= w.start && t < w.end + 0.02;
          const pop = spring({
            frame: Math.max(0, Math.round((t - w.start) * fps)),
            fps,
            config: { damping: 11, stiffness: 240, mass: 0.55 },
            durationInFrames: Math.round(0.28 * fps),
          });
          const scale = speaking
            ? interpolate(pop, [0, 1], [1.0, w.emphasis ? 1.16 : 1.1])
            : w.emphasis && spoken
            ? 1.08
            : 1;
          const color = w.emphasis
            ? emphasisColor
            : speaking
            ? activeColor
            : "#FFFFFF";
          const dim = spoken ? 1 : 0.42;
          return (
            <span
              key={`${i}-${w.start}`}
              style={{
                display: "inline-block",
                color,
                opacity: dim,
                transform: `scale(${scale})`,
                transformOrigin: "50% 80%",
                textShadow: speaking
                  ? `0 0 ${Math.round(fontSize * 0.45)}px ${color}66, 0 3px 0 rgba(0,0,0,0.55)`
                  : "0 3px 0 rgba(0,0,0,0.55)",
                WebkitTextStroke: `${Math.max(2, Math.round(fontSize * 0.045))}px rgba(0,0,0,0.78)`,
                paintOrder: "stroke fill",
                willChange: "transform",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
