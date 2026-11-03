import React from 'react';
import {AbsoluteFill, Img, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {DownloadIcon} from '../components/Icons';
import {Chip, Dot, FadeUp, RevealWords} from '../components/Text';
import {C, GRAD, MONO, mix} from '../theme';

export const OUTRO_FRAMES = 105;

const POINTS: [string, number][] = [
  ['Free & open source', 26],
  ['Nothing to install on the phone', 31],
  ['Windows 10 & 11', 36],
];

export const Outro: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pop = spring({frame: f, fps, config: {damping: 14}});
  const cta = spring({frame: f - 44, fps, config: {damping: 13}});

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 44,
          opacity: Math.min(1, pop * 1.5),
          transform: `scale(${mix(0.85, 1, pop)})`,
        }}
      >
        <Img
          src={staticFile('icon.jpg')}
          style={{
            width: 170,
            height: 170,
            borderRadius: 44,
            boxShadow: '0 24px 70px rgba(0,0,0,0.5), 0 0 90px rgba(255,120,40,0.4)',
          }}
        />
        <div
          style={{
            fontSize: 124,
            fontWeight: 800,
            letterSpacing: '-0.035em',
            lineHeight: 1.15,
            background: GRAD,
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          DanceRMD
        </div>
      </div>

      <RevealWords
        text="Your Windows PC, at your fingertips."
        start={10}
        style={{fontSize: 44, fontWeight: 700, color: C.soft, marginTop: 34}}
      />

      <div style={{display: 'flex', gap: 18, marginTop: 50}}>
        {POINTS.map(([label, start]) => {
          const p = spring({frame: f - start, fps, config: {damping: 12}});
          return (
            <div key={label} style={{transform: `scale(${p})`, opacity: Math.min(1, p * 2)}}>
              <Chip style={{fontSize: 24, padding: '12px 24px'}}>
                <Dot color={C.ok} />
                {label}
              </Chip>
            </div>
          );
        })}
      </div>

      <div style={{display: 'flex', alignItems: 'center', gap: 34, marginTop: 64}}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '22px 40px',
            borderRadius: 18,
            background: GRAD,
            color: C.ink,
            fontSize: 32,
            fontWeight: 800,
            boxShadow: '0 18px 50px rgba(255,106,38,0.4)',
            transform: `scale(${cta})`,
            opacity: Math.min(1, cta * 2),
          }}
        >
          <DownloadIcon size={32} color={C.ink} />
          Download free
        </div>
        <FadeUp start={52}>
          <div style={{fontFamily: MONO, fontSize: 30, color: C.soft}}>github.com/duypp2509/DanceRMD</div>
        </FadeUp>
      </div>
    </AbsoluteFill>
  );
};
