import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {Frame} from './Frame';
import {BaseProps} from './theme';

export type CompareProps = BaseProps & {items: {label: string; value: number; display: string}[]};

export const Compare: React.FC<CompareProps> = ({title, palette, items}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const shown = items.slice(0, 3);
  const top = Math.max(...shown.map((i) => i.value), 1);
  const colors = [palette.accent, '#ffffff', '#96c8ff'];
  return (
    <Frame title={title} palette={palette}>
      <AbsoluteFill style={{justifyContent: 'center', padding: '0 150px', gap: 34}}>
        {shown.map((item, idx) => {
          const p = interpolate(t, [0.4 + idx * 0.35, 1.6 + idx * 0.35], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          const width = (item.value / top) * 100 * p;
          return (
            <div key={idx}>
              <div style={{fontSize: 40, fontWeight: 700, marginBottom: 8}}>{item.label}</div>
              <div style={{position: 'relative', height: 44, borderRadius: 22, background: 'rgba(0,0,0,0.55)'}}>
                <div style={{height: '100%', width: `${width}%`, minWidth: p > 0 ? 44 : 0, borderRadius: 22, background: colors[idx % 3]}} />
                <div
                  style={{
                    position: 'absolute',
                    left: `calc(${Math.max(width, 4)}% + 16px)`,
                    top: 0,
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    fontSize: 36,
                    fontWeight: 800,
                    opacity: p > 0.6 ? 1 : 0,
                  }}
                >
                  {item.display}
                </div>
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
    </Frame>
  );
};
