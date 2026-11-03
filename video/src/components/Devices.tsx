import React from 'react';
import {Img, staticFile} from 'remotion';

/** Screenshots in public/ are 585 × 1266 (portrait) and 1266 × 585 (landscape). */
export const PHONE_RATIO = 1266 / 585;

export const ScreenImg: React.FC<{src: string; style?: React.CSSProperties}> = ({src, style}) => (
  <Img
    src={staticFile(src)}
    style={{
      position: 'absolute',
      inset: 0,
      width: '100%',
      height: '100%',
      objectFit: 'cover',
      objectPosition: 'top',
      ...style,
    }}
  />
);

export const Phone: React.FC<{
  width: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({width, children, style}) => {
  const height = Math.round(width * PHONE_RATIO);
  const bezel = Math.round(width * 0.036);
  return (
    <div
      style={{
        width,
        height,
        padding: bezel,
        borderRadius: width * 0.15,
        background: 'linear-gradient(145deg, #2f241c, #0d0a08)',
        boxShadow:
          '0 0 0 2px #3d2e24, 0 40px 90px rgba(0,0,0,0.6), 0 0 120px rgba(255,120,40,0.18)',
        ...style,
      }}
    >
      <div
        style={{
          width,
          height,
          borderRadius: width * 0.12,
          overflow: 'hidden',
          position: 'relative',
          background: '#000',
        }}
      >
        {children}
        {/* Front camera */}
        <div
          style={{
            position: 'absolute',
            top: width * 0.028,
            left: '50%',
            width: width * 0.036,
            height: width * 0.036,
            marginLeft: -width * 0.018,
            borderRadius: '50%',
            background: '#050403',
            boxShadow: '0 0 0 2px #1a1310',
          }}
        />
      </div>
    </div>
  );
};

export const Laptop: React.FC<{
  width: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({width, children, style}) => {
  const height = Math.round(width / 1.6);
  const bezel = Math.round(width * 0.022);
  const base = width * 1.16 + bezel * 2;
  return (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', ...style}}>
      <div
        style={{
          width,
          height,
          padding: bezel,
          paddingBottom: bezel * 1.5,
          background: 'linear-gradient(180deg, #241b16, #100c0a)',
          borderRadius: `${bezel * 1.4}px ${bezel * 1.4}px 6px 6px`,
          boxShadow:
            '0 0 0 2px #3d2e24, 0 50px 100px rgba(0,0,0,0.55), 0 0 140px rgba(255,120,40,0.14)',
        }}
      >
        <div
          style={{
            width,
            height,
            overflow: 'hidden',
            borderRadius: 6,
            background: '#000',
            position: 'relative',
          }}
        >
          {children}
        </div>
      </div>
      <div
        style={{
          width: base,
          height: width * 0.03,
          background: 'linear-gradient(180deg, #3d2f26, #1a1410 60%, #0e0b09)',
          borderRadius: `4px 4px ${width * 0.03}px ${width * 0.03}px`,
          position: 'relative',
          boxShadow: '0 30px 60px rgba(0,0,0,0.5)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: 0,
            width: width * 0.16,
            height: width * 0.009,
            marginLeft: -width * 0.08,
            background: '#120e0b',
            borderRadius: '0 0 8px 8px',
          }}
        />
      </div>
    </div>
  );
};

/** A fingertip on a touchscreen. */
export const Finger: React.FC<{x: number; y: number; opacity?: number; size?: number}> = ({
  x,
  y,
  opacity = 1,
  size = 44,
}) => (
  <div
    style={{
      position: 'absolute',
      left: x - size / 2,
      top: y - size / 2,
      width: size,
      height: size,
      borderRadius: '50%',
      background: 'rgba(255,255,255,0.32)',
      border: '2px solid rgba(255,255,255,0.92)',
      boxShadow: '0 0 24px rgba(255,138,61,0.7)',
      opacity,
    }}
  />
);

/** An expanding ring, `t` from 0 to 1. */
export const Ripple: React.FC<{x: number; y: number; t: number; max?: number}> = ({
  x,
  y,
  t,
  max = 70,
}) => {
  if (t <= 0 || t >= 1) return null;
  const r = max * t;
  return (
    <div
      style={{
        position: 'absolute',
        left: x - r,
        top: y - r,
        width: r * 2,
        height: r * 2,
        borderRadius: '50%',
        border: '3px solid rgba(255,178,56,0.9)',
        opacity: 1 - t,
      }}
    />
  );
};
