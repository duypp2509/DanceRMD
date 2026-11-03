import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {Background} from './components/Background';
import {CONNECT_FRAMES, Connect} from './scenes/Connect';
import {FEATURES_FRAMES, Features} from './scenes/Features';
import {INTRO_FRAMES, Intro} from './scenes/Intro';
import {OUTRO_FRAMES, Outro} from './scenes/Outro';
import {REMOTE_FRAMES, Remote} from './scenes/Remote';
import {C, FONT} from './theme';

const SCENES: [React.FC, number][] = [
  [Intro, INTRO_FRAMES],
  [Connect, CONNECT_FRAMES],
  [Features, FEATURES_FRAMES],
  [Remote, REMOTE_FRAMES],
  [Outro, OUTRO_FRAMES],
];

export const PROMO_FRAMES = SCENES.reduce((sum, [, frames]) => sum + frames, 0);

export const Promo: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{fontFamily: FONT, color: C.text}}>
      <Background />
      {SCENES.map(([Scene, frames], i) => {
        const start = from;
        from += frames;
        return (
          <Sequence key={i} from={start} durationInFrames={frames}>
            <Scene />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
