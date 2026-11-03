import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Laptop, Phone, ScreenImg} from '../components/Devices';
import {LockIcon} from '../components/Icons';
import {FadeUp, RevealWords} from '../components/Text';
import {C, exitAt, progress} from '../theme';

export const REMOTE_FRAMES = 105;

// Arc from the laptop to the phone (quadratic Bézier)
// Both ends start behind the devices, so the line comes out of them
const P0 = [880, 520];
const P1 = [1180, 180];
const P2 = [1500, 520];
const at = (t: number) => [
  (1 - t) ** 2 * P0[0] + 2 * (1 - t) * t * P1[0] + t ** 2 * P2[0],
  (1 - t) ** 2 * P0[1] + 2 * (1 - t) * t * P1[1] + t ** 2 * P2[1],
];
const APEX = at(0.5);

const Label: React.FC<{x: number; y: number; title: string; sub: string; start: number}> = ({
  x,
  y,
  title,
  sub,
  start,
}) => (
  <div style={{position: 'absolute', left: x, top: y, transform: 'translateX(-50%)', textAlign: 'center'}}>
    <FadeUp start={start} distance={16}>
      <div style={{fontSize: 28, fontWeight: 700, whiteSpace: 'nowrap'}}>{title}</div>
      <div style={{fontSize: 22, color: C.muted, marginTop: 6, fontWeight: 500, whiteSpace: 'nowrap'}}>{sub}</div>
    </FadeUp>
  </div>
);

export const Remote: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const laptopIn = progress(f, 0, 24);
  const phoneIn = progress(f, 6, 24);
  const draw = progress(f, 16, 26);
  const badge = spring({frame: f - 30, fps, config: {damping: 12}});
  const out = exitAt(f, REMOTE_FRAMES, 14);

  // Video goes to the phone, touches come back to the PC
  const packets: {t: number; color: string; r: number}[] = [];
  if (f > 40) {
    for (let k = 0; k < 3; k++) packets.push({t: ((f - 40) / 34 + k / 3) % 1, color: C.amber, r: 9});
    for (let k = 0; k < 2; k++) packets.push({t: 1 - (((f - 40) / 44 + k / 2) % 1), color: '#ffffff', r: 6});
  }

  return (
    <AbsoluteFill style={{opacity: 1 - out}}>
      <div style={{position: 'absolute', top: 92, left: 0, right: 0, textAlign: 'center'}}>
        <RevealWords
          text="Works from anywhere."
          start={4}
          style={{fontSize: 74, fontWeight: 800, letterSpacing: '-0.025em'}}
        />
        <FadeUp start={16}>
          <div style={{fontSize: 30, color: C.muted, marginTop: 18, fontWeight: 500}}>
            One switch starts a secure HTTPS tunnel. No port forwarding, no account.
          </div>
        </FadeUp>
      </div>

      <svg width={1920} height={1080} style={{position: 'absolute', inset: 0}}>
        <defs>
          <mask id="reveal">
            <path
              d={`M ${P0} Q ${P1} ${P2}`}
              stroke="#fff"
              strokeWidth={14}
              fill="none"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - draw}
            />
          </mask>
        </defs>
        <path
          d={`M ${P0} Q ${P1} ${P2}`}
          stroke={C.accent}
          strokeOpacity={0.75}
          strokeWidth={4}
          strokeLinecap="round"
          strokeDasharray="2 16"
          fill="none"
          mask="url(#reveal)"
        />
        {packets.map((p, i) => {
          const [x, y] = at(p.t);
          return <circle key={i} cx={x} cy={y} r={p.r} fill={p.color} style={{filter: `drop-shadow(0 0 10px ${p.color})`}} />;
        })}
      </svg>

      <Laptop
        width={640}
        style={{
          position: 'absolute',
          left: 250,
          top: 420,
          opacity: laptopIn,
          transform: `translateX(${(1 - laptopIn) * -80}px)`,
        }}
      >
        <ScreenImg src="dashboard.png" />
      </Laptop>
      <Phone
        width={200}
        style={{
          position: 'absolute',
          left: 1470,
          top: 400,
          opacity: phoneIn,
          transform: `translateX(${(1 - phoneIn) * 80}px)`,
        }}
      >
        <ScreenImg src="phone-touchpad.png" />
      </Phone>

      <div
        style={{
          position: 'absolute',
          left: APEX[0],
          top: APEX[1],
          transform: `translate(-50%, -50%) scale(${badge})`,
          opacity: Math.min(1, badge * 2),
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '14px 26px',
          borderRadius: 999,
          background: 'rgba(21,16,12,0.96)',
          border: `1.5px solid ${C.accent}`,
          boxShadow: '0 0 40px rgba(255,138,61,0.35)',
          fontSize: 24,
          fontWeight: 700,
          whiteSpace: 'nowrap',
          color: C.text,
        }}
      >
        <LockIcon size={26} color={C.accent} />
        Cloudflare HTTPS tunnel
      </div>

      <Label x={250 + 320 + 14} y={890} title="Your PC" sub="at home or at the office" start={34} />
      <Label x={1470 + 107} y={890} title="Your phone" sub="on any Wi-Fi or 4G/5G" start={40} />
    </AbsoluteFill>
  );
};
