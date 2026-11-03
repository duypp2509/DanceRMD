import {loadFont} from '@remotion/google-fonts/PlusJakartaSans';
import {Easing, interpolate} from 'remotion';

// Same font and colors as the website (website/css/styles.css)
const {fontFamily} = loadFont('normal', {
  weights: ['500', '600', '700', '800'],
  subsets: ['latin', 'latin-ext', 'vietnamese'],
});

export const FONT = fontFamily;
export const MONO = '"Cascadia Code", Consolas, ui-monospace, monospace';

export const C = {
  bg: '#0c0907',
  surface: '#15100c',
  raised: '#1f1712',
  line: '#2e231b',
  lineStrong: '#45342a',
  text: '#f6efe9',
  soft: '#d4c7bc',
  muted: '#a8998c',
  accent: '#ff8a3d',
  amber: '#ffb238',
  hot: '#ff5a1f',
  ok: '#34c77b',
  ink: '#1b0e04',
};

export const GRAD = 'linear-gradient(90deg, #ff5a1f, #ff8a3d 45%, #ffb238)';

export const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

/** 0 → 1 between `start` and `start + len`, eased. */
export const progress = (frame: number, start: number, len: number, easing = easeOut) =>
  interpolate(frame, [start, start + len], [0, 1], {...CLAMP, easing});

/** 0 before `end - len`, 1 at `end`: drives a scene's exit. */
export const exitAt = (frame: number, end: number, len = 12) =>
  interpolate(frame, [end - len, end], [0, 1], {...CLAMP, easing: easeInOut});

export const mix = (a: number, b: number, t: number) => a + (b - a) * t;
