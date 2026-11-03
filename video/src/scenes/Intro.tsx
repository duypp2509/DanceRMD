import React from 'react';
import {AbsoluteFill, Img, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {RevealWords} from '../components/Text';
import {C, GRAD, easeInOut, exitAt, mix, progress} from '../theme';

export const INTRO_FRAMES = 120;

export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame, fps, config: {damping: 13, mass: 0.8}});
  const reveal = progress(frame, 22, 28, easeInOut);
  const out = exitAt(frame, INTRO_FRAMES, 14);

  return (
    <AbsoluteFill
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        opacity: 1 - out,
        transform: `scale(${1 - out * 0.05})`,
      }}
    >
      <div style={{display: 'flex', alignItems: 'center'}}>
        <Img
          src={staticFile('icon.jpg')}
          style={{
            width: 230,
            height: 230,
            borderRadius: 58,
            opacity: Math.min(1, frame / 8),
            transform: `scale(${mix(0.45, 1, pop)}) rotate(${(1 - pop) * -12}deg)`,
            boxShadow: '0 30px 80px rgba(0,0,0,0.5), 0 0 110px rgba(255,120,40,0.4)',
          }}
        />
        {/* Grows from zero width, so the icon glides left as the name appears */}
        <div style={{maxWidth: 880 * reveal, overflow: 'hidden'}}>
          <div
            style={{
              paddingLeft: 56,
              fontSize: 150,
              fontWeight: 800,
              letterSpacing: '-0.035em',
              lineHeight: 1.15,
              whiteSpace: 'nowrap',
              background: GRAD,
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              opacity: reveal,
              transform: `translateX(${(1 - reveal) * -70}px)`,
            }}
          >
            DanceRMD
          </div>
        </div>
      </div>
      <RevealWords
        text="Your Windows PC, at your fingertips."
        start={54}
        style={{
          fontSize: 60,
          fontWeight: 700,
          letterSpacing: '-0.015em',
          marginTop: 60,
          color: C.text,
        }}
      />
    </AbsoluteFill>
  );
};
