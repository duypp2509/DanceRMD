# DanceRMD website

The product landing page for DanceRMD. It is a static site — plain HTML, CSS and a little vanilla
JavaScript — with no build step and no third-party scripts (the only external request is the
Plus Jakarta Sans font from Google Fonts).

## Structure

```
website/
├── index.html          Landing page
├── 404.html            Not-found page (self-contained styles)
├── robots.txt
├── css/styles.css      All styles; design tokens live at the top in :root
├── js/main.js          Progressive enhancements: mobile menu, scroll reveal, code rain, video autoplay
├── assets/             Logos, favicons, Open Graph card, mascot (generated), product video
└── tools/make_assets.py
```

The page works without JavaScript; scripts only add the collapsible mobile menu, reveal
animations and the decorative code rain. All motion is disabled when the visitor prefers
reduced motion.

## Preview locally

From the repository root:

```bash
python -m http.server -d website 8000
```

Then open <http://localhost:8000>. (The 404 page uses `<base href="/DanceRMD/">` to match the
GitHub Pages URL, so its links only resolve once deployed.)

## Regenerate images

All images in `assets/` are generated from the mascot artwork at
`dancermd/resources/icon.jpg`:

```bash
python website/tools/make_assets.py
```

Requires Pillow. Re-run it whenever the artwork changes and commit the results.

The product video (`assets/promo.mp4` and its poster `assets/promo-poster.jpg`) is not made by
that script. It is rendered from the Remotion project in `video/`, then compressed for the web:

```bash
cd video && npm run render && cd ..
ffmpeg -i video/out/DanceRMD-promo.mp4 -an -vf "scale=out_range=tv,format=yuv420p" \
  -c:v libx264 -preset slow -crf 25 -movflags +faststart website/assets/promo.mp4
ffmpeg -ss 3.47 -i video/out/DanceRMD-promo.mp4 -frames:v 1 -q:v 4 website/assets/promo-poster.jpg
```

On the page the video starts when it scrolls into view and pauses when it leaves, so it only
downloads for visitors who reach it. With reduced motion it does not autoplay.

## Deployment

`.github/workflows/pages.yml` publishes this folder to GitHub Pages on every push to `main`
that touches `website/**` (or manually via *Run workflow*). One-time setup in the repository:
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

The site is then served at `https://duypp2509.github.io/DanceRMD/`.

## Changing the repository or domain

If the repository is renamed, forked or moved to a custom domain, update:

| What | Where |
| --- | --- |
| Repository links | `REPO_URL` in `js/main.js` (links also carry plain `href` fallbacks in `index.html` for visitors without JavaScript) |
| Social preview URLs | `og:url`, `og:image` and `twitter:image` in `index.html` |
| Not-found page base path | `<base href>` in `404.html` |

The **Download** buttons point at `…/releases/latest`, so they work as soon as a GitHub release with
`DanceRMD.exe` attached is published.
