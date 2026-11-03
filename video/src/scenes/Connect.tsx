import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Laptop, Phone, ScreenImg} from '../components/Devices';
import {CheckIcon} from '../components/Icons';
import {FadeUp, RevealWords} from '../components/Text';
import {C, CLAMP, exitAt, mix, progress} from '../theme';

export const CONNECT_FRAMES = 150;

const SCANNED = 76; // the frame where the camera locks onto the QR code
const PHONE_W = 300;
const PHONE_H = Math.round(PHONE_W * (1266 / 585));

/** The phone camera pointed at the QR code on the dashboard. */
const CameraView: React.FC<{frame: number}> = ({frame}) => {
  const lock = progress(frame, SCANNED - 8, 10);
  const shake = 1 - lock;
  const dx = Math.sin(frame / 13) * 6 * shake;
  const dy = Math.cos(frame / 17) * 5 * shake;

  // dashboard.png is 1320 × 1032; its QR code is centred at (287, 352)
  const zoom = 0.72;
  const cx = PHONE_W / 2;
  const cy = PHONE_H * 0.45;
  const box = mix(270, 252, lock);
  const color = lock > 0.5 ? C.ok : '#ffffff';
  const scanY = (frame * 8) % box;

  const corner = (pos: React.CSSProperties, sides: string[]) => (
    <div
      style={{
        position: 'absolute',
        width: 44,
        height: 44,
        ...pos,
        ...Object.fromEntries(sides.map((s) => [`border${s}`, `5px solid ${color}`])),
        [`border${sides[0]}${sides[1]}Radius`]: 14,
      }}
    />
  );

  return (
    <AbsoluteFill style={{background: '#111'}}>
      <Img
        src={staticFile('dashboard.png')}
        style={{
          position: 'absolute',
          width: 1320 * zoom,
          left: cx - 287 * zoom + dx,
          top: cy - 352 * zoom + dy,
          filter: 'brightness(0.92) contrast(1.05)',
        }}
      />
      <AbsoluteFill
        style={{background: 'radial-gradient(circle at 50% 45%, transparent 38%, rgba(0,0,0,0.7) 100%)'}}
      />
      <div
        style={{
          position: 'absolute',
          left: cx - box / 2,
          top: cy - box / 2,
          width: box,
          height: box,
        }}
      >
        {corner({left: 0, top: 0}, ['Top', 'Left'])}
        {corner({right: 0, top: 0}, ['Top', 'Right'])}
        {corner({left: 0, bottom: 0}, ['Bottom', 'Left'])}
        {corner({right: 0, bottom: 0}, ['Bottom', 'Right'])}
        {lock < 0.5 && (
          <div
            style={{
              position: 'absolute',
              left: 10,
              right: 10,
              top: scanY,
              height: 3,
              background: `linear-gradient(90deg, transparent, ${C.accent}, transparent)`,
              boxShadow: `0 0 18px ${C.accent}`,
            }}
          />
        )}
      </div>
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: cy + box / 2 + 30,
          transform: 'translateX(-50%)',
          padding: '8px 16px',
          borderRadius: 999,
          background: 'rgba(0,0,0,0.78)',
          fontSize: 16,
          fontWeight: 700,
          whiteSpace: 'nowrap',
          color: lock > 0.5 ? C.ok : '#ffffff',
        }}
      >
        {lock > 0.5 ? 'DanceRMD found' : 'Point at the QR code'}
      </div>
    </AbsoluteFill>
  );
};

export const Connect: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const laptopIn = progress(frame, 0, 26);
  const phoneIn = progress(frame, 14, 32);
  const flash = interpolate(frame, [SCANNED + 4, SCANNED + 8, SCANNED + 20], [0, 0.85, 0], CLAMP);
  const connected = frame >= SCANNED + 8;
  const toast = spring({frame: frame - (SCANNED + 14), fps, config: {damping: 12}});
  const out = exitAt(frame, CONNECT_FRAMES, 14);

  return (
    <AbsoluteFill style={{opacity: 1 - out}}>
      <div style={{position: 'absolute', top: 92, left: 0, right: 0, textAlign: 'center'}}>
        <RevealWords
          text="Scan the QR code. You're in."
          start={4}
          style={{fontSize: 74, fontWeight: 800, letterSpacing: '-0.025em'}}
        />
        <FadeUp start={18}>
          <div style={{fontSize: 30, color: C.muted, marginTop: 18, fontWeight: 500}}>
            Nothing to install on the phone. It is just the browser.
          </div>
        </FadeUp>
      </div>

      <Laptop
        width={860}
        style={{
          position: 'absolute',
          left: 340,
          top: 336,
          opacity: laptopIn,
          transform: `translateY(${(1 - laptopIn) * 70}px)`,
        }}
      >
        <ScreenImg src="dashboard.png" />
      </Laptop>

      <div
        style={{
          position: 'absolute',
          left: 1310,
          top: 300,
          opacity: phoneIn,
          transform: `translateX(${(1 - phoneIn) * 460}px) rotate(${mix(12, -4, phoneIn)}deg)`,
        }}
      >
        <Phone width={PHONE_W}>
          {connected ? <ScreenImg src="phone-touchpad.png" /> : <CameraView frame={frame} />}
          <AbsoluteFill style={{background: '#fff', opacity: flash}} />
        </Phone>
        {toast > 0.01 && (
          <div
            style={{
              position: 'absolute',
              left: -150,
              top: 120,
              transform: `scale(${toast})`,
              transformOrigin: 'right center',
              opacity: Math.min(1, toast * 2),
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '16px 26px 16px 18px',
              borderRadius: 999,
              background: 'rgba(21,16,12,0.95)',
              border: `1.5px solid ${C.lineStrong}`,
              boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
              fontSize: 26,
              fontWeight: 700,
              whiteSpace: 'nowrap',
            }}
          >
            <span
              style={{
                width: 38,
                height: 38,
                borderRadius: 19,
                background: C.ok,
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <CheckIcon size={22} color="#06210f" />
            </span>
            Connected
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
