export type Palette = {c1: string; c2: string; accent: string};

export const DEFAULT_PALETTE: Palette = {c1: '#141a3a', c2: '#2b3a8f', accent: '#ffc857'};

export const FONT = 'Inter, "Helvetica Neue", Arial, sans-serif';

export type BaseProps = {
  title: string;
  durationSec: number;
  palette: Palette;
};
