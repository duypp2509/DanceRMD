# DanceRMD promo video

A 30-second motion graphic (1920 × 1080, 30 fps, no audio) made with [Remotion](https://www.remotion.dev/).

```
npm install
npm run studio   # live preview with a timeline, in the browser
npm run render   # writes out/DanceRMD-promo.mp4
```

| Scene | Frames | File |
|---|---|---|
| Logo and tagline | 0–120 | `src/scenes/Intro.tsx` |
| Scan the QR code | 120–270 | `src/scenes/Connect.tsx` |
| Streaming, touchpad, keyboard, window switcher | 270–690 | `src/scenes/Features.tsx` |
| Remote access | 690–795 | `src/scenes/Remote.tsx` |
| Call to action | 795–900 | `src/scenes/Outro.tsx` |

Colors and font follow the website (`src/theme.ts`). The screenshots in `public/` are copies of `docs/images/`.
