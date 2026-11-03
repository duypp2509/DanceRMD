import React, {useMemo} from 'react';
import {AbsoluteFill, random, useCurrentFrame} from 'remotion';
import {C, MONO} from '../theme';

const GLYPHS = '0123456789ABCDEF{}<>=;()';
const COLUMNS = 40;
const ROWS = 34;
const ROW_H = 34;

/** Warm glow and slow code rain, the website's hero motif. */
export const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const columns = useMemo(
    () =>
      Array.from({length: COLUMNS}, (_, i) => ({
        x: i * 48 + 14,
        speed: 0.4 + random(`speed-${i}`) * 1.1,
        offset: random(`offset-${i}`) * ROWS * ROW_H,
        hidden: random(`hidden-${i}`) < 0.3,
        text: Array.from(
          {length: ROWS},
          (_, r) => GLYPHS[Math.floor(random(`glyph-${i}-${r}`) * GLYPHS.length)],
        ).join('\n'),
      })),
    [],
  );

  const gx = 30 + Math.sin(frame / 80) * 6;
  const gy = 40 + Math.cos(frame / 95) * 5;
  const loop = ROWS * ROW_H;

  return (
    <AbsoluteFill style={{background: C.bg, overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(1000px 760px at ${gx}% ${gy}%, rgba(255,106,38,0.26), transparent 70%),
            radial-gradient(900px 640px at 86% 92%, rgba(255,178,56,0.10), transparent 70%)`,
        }}
      />
      {columns.map((c, i) => {
        if (c.hidden) return null;
        // Stronger towards the edges so the middle stays calm behind the content
        const edge = Math.abs(c.x + 10 - 960) / 960;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: c.x,
              top: 0,
              transform: `translateY(${((c.offset + frame * c.speed) % loop) - loop}px)`,
              fontFamily: MONO,
              fontSize: 22,
              lineHeight: `${ROW_H}px`,
              color: C.amber,
              opacity: 0.03 + 0.12 * edge * edge,
              whiteSpace: 'pre',
            }}
          >
            {c.text + '\n' + c.text}
          </div>
        );
      })}
      <AbsoluteFill
        style={{
          background: 'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};
