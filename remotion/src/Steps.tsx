import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Frame} from './Frame';
import {BaseProps} from './theme';

export type StepsProps = BaseProps & {items: string[]};

export const Steps: React.FC<StepsProps> = ({title, palette, items}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  return (
    <Frame title={title} palette={palette}>
      <AbsoluteFill style={{justifyContent: 'center', padding: '60px 180px 0', gap: 26}}>
        {items.slice(0, 5).map((text, idx) => {
          const p = interpolate(t, [0.4 + idx * 0.6, 0.9 + idx * 0.6], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.back(1.6)),
          });
          return (
            <div
              key={idx}
              style={{display: 'flex', alignItems: 'center', gap: 28, opacity: Math.min(1, p * 2), transform: `translateX(${(1 - p) * -80}px)`}}
            >
              <div
                style={{
                  width: 62,
                  height: 62,
                  borderRadius: 31,
                  background: palette.accent,
                  color: '#000',
                  fontSize: 36,
                  fontWeight: 900,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {idx + 1}
              </div>
              <div style={{fontSize: 46, fontWeight: 700}}>{text}</div>
            </div>
          );
        })}
      </AbsoluteFill>
    </Frame>
  );
};
