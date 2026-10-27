import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Frame} from './Frame';
import {BaseProps} from './theme';

export type CounterProps = BaseProps & {value: number; prefix: string; suffix: string; decimals: number};

const format = (v: number, decimals: number) => {
  const [int, dec] = v.toFixed(decimals).split('.');
  const withDots = int.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return dec ? `${withDots},${dec}` : withDots;
};

export const Counter: React.FC<CounterProps> = ({title, palette, value, prefix, suffix, decimals}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const progress = interpolate(t, [0.3, 2.1], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const pop = 1 + 0.06 * Math.sin(interpolate(t, [2.1, 2.45], [0, Math.PI], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const barW = interpolate(t, [0.2, 1.0], [0, 380], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  return (
    <Frame title={title} palette={palette}>
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
        <div
          style={{
            fontSize: 210,
            fontWeight: 900,
            transform: `scale(${pop})`,
            textShadow: '6px 6px 0 rgba(0,0,0,0.85)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {prefix}
          {format(value * progress, decimals)}
          {suffix}
        </div>
        <div style={{marginTop: 30, height: 10, width: barW, borderRadius: 5, background: palette.accent}} />
      </AbsoluteFill>
    </Frame>
  );
};
