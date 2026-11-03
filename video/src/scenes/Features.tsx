import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Finger, PHONE_RATIO, Phone, Ripple, ScreenImg} from '../components/Devices';
import {Caption, Chip, Dot} from '../components/Text';
import {C, CLAMP, MONO, easeInOut, exitAt, mix, progress} from '../theme';

export const FEATURES_FRAMES = 420;

// Four beats of 105 frames on one phone: streaming, touchpad, keyboard, window switcher
const PHONE_W = 340;
const PHONE_H = Math.round(PHONE_W * PHONE_RATIO);
const CENTER_X = 1340;
const CENTER_Y = 540;
const S = PHONE_W / 585; // screenshot pixels → screen pixels

const quad = (a: number[], b: number[], c: number[], t: number) => [
  (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * b[0] + t ** 2 * c[0],
  (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * b[1] + t ** 2 * c[1],
];

/** Beat 2: tap, drag, two-finger scroll on the touchpad. */
const TouchGestures: React.FC<{f: number}> = ({f}) => {
  const items: React.ReactNode[] = [];
  // Tap twice
  if (f >= 112 && f < 138) {
    const fade = interpolate(f, [112, 116, 132, 138], [0, 1, 1, 0], CLAMP);
    items.push(<Finger key="tap" x={175} y={290} opacity={fade} />);
    items.push(<Ripple key="r1" x={175} y={290} t={(f - 117) / 14} />);
    items.push(<Ripple key="r2" x={175} y={290} t={(f - 125) / 14} />);
  }
  // Drag along a curve, leaving a glowing trail
  if (f >= 138 && f < 176) {
    const fade = interpolate(f, [138, 142, 170, 176], [0, 1, 1, 0], CLAMP);
    const t = progress(f, 140, 30, easeInOut);
    const path = (u: number) => quad([95, 500], [110, 260], [255, 230], u);
    const points = Array.from({length: 24}, (_, i) => path((t * i) / 23).join(',')).join(' ');
    items.push(
      <svg key="trail" width={PHONE_W} height={PHONE_H} style={{position: 'absolute', inset: 0, opacity: fade * 0.8}}>
        <polyline
          points={points}
          fill="none"
          stroke={C.amber}
          strokeWidth={6}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{filter: `drop-shadow(0 0 8px ${C.accent})`}}
        />
      </svg>,
    );
    const [x, y] = path(t);
    items.push(<Finger key="drag" x={x} y={y} opacity={fade} />);
  }
  // Two-finger scroll
  if (f >= 176 && f < 208) {
    const fade = interpolate(f, [176, 180, 202, 208], [0, 1, 1, 0], CLAMP);
    const y = mix(520, 330, progress(f, 180, 22, easeInOut));
    items.push(<Finger key="s1" x={140} y={y} opacity={fade} />);
    items.push(<Finger key="s2" x={205} y={y + 10} opacity={fade} />);
  }
  // Beat 4: three-finger swipe up opens the window switcher
  if (f >= 340 && f < 366) {
    const fade = interpolate(f, [340, 344, 360, 366], [0, 1, 1, 0], CLAMP);
    const y = mix(600, 400, progress(f, 343, 18, easeInOut));
    [110, 170, 230].forEach((x, i) => items.push(<Finger key={`t${i}`} x={x} y={y + (i === 1 ? -14 : 0)} opacity={fade} />));
  }
  return <>{items}</>;
};

const GESTURES: [number, number, string][] = [
  [112, 138, 'Tap to click'],
  [138, 176, 'Drag'],
  [176, 208, 'Two-finger scroll'],
  [340, 372, 'Three-finger swipe up'],
];

const GestureLabel: React.FC<{f: number}> = ({f}) => {
  const current = GESTURES.find(([a, b]) => f >= a && f < b);
  if (!current) return null;
  const [a, b, label] = current;
  const p = interpolate(f, [a, a + 6, b - 6, b], [0, 1, 1, 0], CLAMP);
  return (
    <div
      style={{
        position: 'absolute',
        left: CENTER_X,
        top: CENTER_Y + PHONE_H / 2 + 46,
        transform: `translateX(-50%) translateY(${(1 - p) * 12}px)`,
        opacity: p,
      }}
    >
      <Chip style={{fontSize: 24, padding: '12px 24px'}}>
        <Dot color={C.amber} />
        {label}
      </Chip>
    </div>
  );
};

/** Beat 1: encoder chips float around the phone. */
const StreamChips: React.FC<{f: number}> = ({f}) => {
  const {fps} = useVideoConfig();
  const chips: [string, number, number, number][] = [
    ['NVENC', 975, 200, 16],
    ['Quick Sync', 1580, 330, 22],
    ['AMF', 960, 830, 28],
    ['H.264 · WebCodecs', 1560, 640, 34],
  ];
  const out = progress(f, 92, 12);
  return (
    <>
      {chips.map(([label, x, y, start], i) => {
        const pop = spring({frame: f - start, fps, config: {damping: 12}});
        return (
          <div
            key={label}
            style={{
              position: 'absolute',
              left: x,
              top: y + Math.sin((f + i * 20) / 16) * 8,
              transform: `scale(${pop * (1 - out * 0.2)})`,
              opacity: Math.min(1, pop * 2) * (1 - out),
            }}
          >
            <Chip style={{color: C.amber}}>
              <Dot color={C.ok} />
              {label}
            </Chip>
          </div>
        );
      })}
    </>
  );
};

const TYPED = 'Xin chào thế giới';

/** Beat 3: live typing, in the phone's text box and on the PC at the same time. */
const Typing: React.FC<{f: number}> = ({f}) => {
  const count = Math.floor(interpolate(f, [244, 292], [0, TYPED.length], CLAMP));
  const text = TYPED.slice(0, count);
  const caret = Math.floor(f / 8) % 2 === 0;
  // Landscape screenshot 1266 × 585, shown at 736 × 340: the text box is at (602, 93)–(1020, 158)
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 602 * S + 12,
          top: 93 * S,
          height: 65 * S,
          display: 'flex',
          alignItems: 'center',
          fontSize: 17,
          fontWeight: 600,
          color: C.text,
          whiteSpace: 'nowrap',
        }}
      >
        {text}
        <span style={{width: 2, height: 20, marginLeft: 2, background: C.accent, opacity: caret ? 1 : 0}} />
      </div>
      {count > 0 && (
        <div
          style={{
            position: 'absolute',
            left: 175 * S,
            top: 368 * S,
            padding: '3px 8px',
            background: '#1e1e1e',
            border: `1px solid ${C.accent}`,
            borderRadius: 4,
            fontFamily: MONO,
            fontSize: 13,
            color: '#f2f2f2',
            whiteSpace: 'nowrap',
            boxShadow: `0 0 16px rgba(255,138,61,0.45)`,
          }}
        >
          {text}
        </div>
      )}
    </>
  );
};

export const Features: React.FC = () => {
  const f = useCurrentFrame();
  const enter = progress(f, 0, 26);
  const out = exitAt(f, FEATURES_FRAMES, 14);

  // Turn to landscape for the keyboard, then back
  const land = progress(f, 212, 26, easeInOut) - progress(f, 316, 26, easeInOut);
  // Like a real phone, the screen goes dark mid-turn and swaps layouts behind it
  const landContent = land >= 0.5 ? 1 : 0;
  const blackout = interpolate(land, [0.15, 0.5, 0.85], [0, 1, 0], CLAMP);
  const switcher = progress(f, 356, 22);

  return (
    <AbsoluteFill style={{opacity: 1 - out}}>
      <Caption
        start={6}
        end={103}
        eyebrow="01 · GPU streaming"
        title={'Your PC screen,\nsmooth on your phone.'}
        sub="Hardware H.264 from NVIDIA, Intel or AMD, decoded by the phone itself. Frames are sent only when something changes."
      />
      <Caption
        start={109}
        end={208}
        eyebrow="02 · Touchpad"
        title={'A real touchpad\nin your hand.'}
        sub="Tap, drag, right-click, two-finger scroll and pinch to zoom. Or switch to direct touch."
      />
      <Caption
        start={214}
        end={313}
        eyebrow="03 · Keyboard"
        title={'Type in any\nlanguage.'}
        sub="Live typing works with every phone keyboard, Vietnamese included, plus shortcuts and F-keys."
      />
      <Caption
        start={319}
        end={430}
        eyebrow="04 · Window switcher"
        title={'Alt+Tab,\nfrom your phone.'}
        sub="Live thumbnails of every open window. Swipe with three fingers to switch."
      />

      <StreamChips f={f} />

      <div
        style={{
          position: 'absolute',
          left: CENTER_X,
          top: CENTER_Y,
          opacity: enter,
          transform: `translate(-50%, -50%) translateY(${(1 - enter) * 90}px) scale(${
            mix(0.94, 1, enter) * mix(1, 1.06, land)
          }) rotate(${-90 * land}deg)`,
        }}
      >
        <Phone width={PHONE_W}>
          <ScreenImg src="phone-touchpad.png" />
          {switcher > 0 && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                opacity: switcher,
                transform: `translateY(${(1 - switcher) * 140}px)`,
              }}
            >
              <ScreenImg src="phone-switcher.png" />
            </div>
          )}
          {landContent > 0 && (
            // Counter-rotated so it reads upright while the phone is turned
            <div
              style={{
                position: 'absolute',
                width: PHONE_H,
                height: PHONE_W,
                left: (PHONE_W - PHONE_H) / 2,
                top: (PHONE_H - PHONE_W) / 2,
                transform: 'rotate(90deg)',
                opacity: landContent,
                background: '#000',
              }}
            >
              <ScreenImg src="phone-landscape.png" />
              <Typing f={f} />
            </div>
          )}
          {blackout > 0 && <AbsoluteFill style={{background: '#000', opacity: blackout}} />}
          <TouchGestures f={f} />
        </Phone>
      </div>

      <GestureLabel f={f} />
    </AbsoluteFill>
  );
};
