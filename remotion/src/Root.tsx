import React from 'react';
import {Composition} from 'remotion';
import {Compare, CompareProps} from './Compare';
import {Counter, CounterProps} from './Counter';
import {Steps, StepsProps} from './Steps';
import {DEFAULT_PALETTE} from './theme';

const FPS = 30;
const base = {title: 'Título', durationSec: 4, palette: DEFAULT_PALETTE};
const duration = ({props}: {props: {durationSec: number}}) => ({
  durationInFrames: Math.max(1, Math.round(props.durationSec * FPS)),
});

export const Root: React.FC = () => (
  <>
    <Composition
      id="counter"
      component={Counter as React.FC<any>}
      width={1280}
      height={720}
      fps={FPS}
      durationInFrames={FPS * 4}
      defaultProps={{...base, value: 300, prefix: '', suffix: '%', decimals: 0} as CounterProps}
      calculateMetadata={duration as any}
    />
    <Composition
      id="compare"
      component={Compare as React.FC<any>}
      width={1280}
      height={720}
      fps={FPS}
      durationInFrames={FPS * 4}
      defaultProps={{...base, items: [{label: 'A', value: 40, display: '40%'}, {label: 'B', value: 25, display: '25%'}]} as CompareProps}
      calculateMetadata={duration as any}
    />
    <Composition
      id="steps"
      component={Steps as React.FC<any>}
      width={1280}
      height={720}
      fps={FPS}
      durationInFrames={FPS * 4}
      defaultProps={{...base, items: ['Ahorra', 'Invierte', 'Espera']} as StepsProps}
      calculateMetadata={duration as any}
    />
  </>
);
