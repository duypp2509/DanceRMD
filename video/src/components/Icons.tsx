import React from 'react';

const base = {fill: 'none', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round'} as const;

export const LockIcon: React.FC<{size?: number; color?: string}> = ({size = 24, color = 'currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
    <rect x="4" y="10.5" width="16" height="10.5" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </svg>
);

export const DownloadIcon: React.FC<{size?: number; color?: string}> = ({size = 24, color = 'currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base}>
    <path d="M12 4v11" />
    <path d="m7 10.5 5 5 5-5" />
    <path d="M5 20h14" />
  </svg>
);

export const CheckIcon: React.FC<{size?: number; color?: string}> = ({size = 24, color = 'currentColor'}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} {...base} strokeWidth={3}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
);
