import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {PROMO_FRAMES, Promo} from './Promo';

const Root: React.FC = () =>
  React.createElement(Composition, {
    id: 'Promo',
    component: Promo,
    durationInFrames: PROMO_FRAMES,
    fps: 30,
    width: 1920,
    height: 1080,
  });

registerRoot(Root);
