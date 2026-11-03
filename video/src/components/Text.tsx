import React from 'react';
import {useCurrentFrame} from 'remotion';
import {C, progress} from '../theme';

/** Words rise one by one from behind a mask. `\n` starts a new line. */
export const RevealWords: React.FC<{
  text: string;
  start: number;
  stagger?: number;
  len?: number;
  style?: React.CSSProperties;
}> = ({text, start, stagger = 3, len = 22, style}) => {
  const frame = useCurrentFrame();
  let index = 0;
  return (
    <div style={style}>
      {text.split('\n').map((line, li) => {
        const words = line.split(' ');
        return (
          <div key={li}>
            {words.map((word, wi) => {
              const p = progress(frame, start + index++ * stagger, len);
              return (
                <span
                  key={wi}
                  style={{
                    display: 'inline-block',
                    overflow: 'hidden',
                    verticalAlign: 'top',
                    paddingBottom: '0.14em',
                    marginBottom: '-0.14em',
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      transform: `translateY(${(1 - p) * 110}%)`,
                      opacity: Math.min(1, p * 1.6),
                    }}
                  >
                    {word}
                  </span>
                  {wi < words.length - 1 ? ' ' : ''}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export const FadeUp: React.FC<{
  start: number;
  len?: number;
  distance?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({start, len = 20, distance = 28, children, style}) => {
  const frame = useCurrentFrame();
  const p = progress(frame, start, len);
  return (
    <div style={{opacity: p, transform: `translateY(${(1 - p) * distance}px)`, ...style}}>
      {children}
    </div>
  );
};

export const Eyebrow: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 14,
      fontSize: 22,
      fontWeight: 700,
      letterSpacing: '0.16em',
      textTransform: 'uppercase',
      color: C.accent,
    }}
  >
    <span
      style={{
        width: 10,
        height: 10,
        borderRadius: 5,
        background: C.accent,
        boxShadow: `0 0 14px ${C.accent}`,
      }}
    />
    {children}
  </div>
);

export const Chip: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({
  children,
  style,
}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 12,
      padding: '14px 26px',
      borderRadius: 999,
      background: 'rgba(31,23,18,0.92)',
      border: `1.5px solid ${C.lineStrong}`,
      color: C.text,
      fontSize: 26,
      fontWeight: 700,
      whiteSpace: 'nowrap',
      boxShadow: '0 16px 40px rgba(0,0,0,0.35)',
      ...style,
    }}
  >
    {children}
  </div>
);

export const Dot: React.FC<{color?: string}> = ({color = C.accent}) => (
  <span
    style={{
      width: 10,
      height: 10,
      borderRadius: 5,
      background: color,
      boxShadow: `0 0 12px ${color}`,
      flexShrink: 0,
    }}
  />
);

/** Feature caption on the left half of the frame. */
export const Caption: React.FC<{
  eyebrow: string;
  title: string;
  sub: string;
  start: number;
  end: number;
}> = ({eyebrow, title, sub, start, end}) => {
  const frame = useCurrentFrame();
  if (frame < start - 1 || frame > end) return null;
  const out = progress(frame, end - 10, 10);
  return (
    <div
      style={{
        position: 'absolute',
        left: 150,
        top: '50%',
        width: 900,
        transform: `translateY(-50%) translateY(${-out * 26}px)`,
        opacity: 1 - out,
      }}
    >
      <FadeUp start={start} distance={16}>
        <Eyebrow>{eyebrow}</Eyebrow>
      </FadeUp>
      <RevealWords
        text={title}
        start={start + 4}
        style={{
          fontSize: 76,
          fontWeight: 800,
          lineHeight: 1.06,
          letterSpacing: '-0.025em',
          marginTop: 26,
        }}
      />
      <FadeUp start={start + 16}>
        <div
          style={{
            fontSize: 30,
            lineHeight: 1.45,
            color: C.muted,
            marginTop: 30,
            fontWeight: 500,
            maxWidth: 740,
          }}
        >
          {sub}
        </div>
      </FadeUp>
    </div>
  );
};
