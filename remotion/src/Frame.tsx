import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONT, Palette} from './theme';

// Fondo con degradado y un destello que se desplaza, más el título que entra con desvanecido.
export const Frame: React.FC<{title: string; palette: Palette; children: React.ReactNode}> = ({
  title,
  palette,
  children,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const t = frame / fps;
  const glowX = 15 + 70 * ((t * 0.08) % 1);
  const fadeIn = interpolate(frame, [0, 0.5 * fps], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const fadeOut = interpolate(frame, [durationInFrames - 0.3 * fps, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${palette.c1}, ${palette.c2})`,
        fontFamily: FONT,
        color: 'white',
        opacity: fadeOut,
      }}
    >
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${glowX}% 0%, ${palette.accent}33, transparent 45%)`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 52,
          width: '100%',
          textAlign: 'center',
          fontSize: 44,
          fontWeight: 800,
          letterSpacing: 1,
          textTransform: 'uppercase',
          opacity: fadeIn * 0.9,
          transform: `translateY(${(1 - fadeIn) * -24}px)`,
        }}
      >
        {title}
      </div>
      {children}
    </AbsoluteFill>
  );
};
