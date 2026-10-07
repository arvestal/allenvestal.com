const fs = require('fs');
const path = require('path');
const express = require('express');

const { requireAdmin } = require('../lib/require-admin');

// Private CF26 scouting pages (cf26/ in this repo, built by cf26/scripts/render_html.py).
// Same Google login as /admin; only the generated HTML pages are served, never the raw data
// files next to them. The pages are self-contained (inline CSS/JS) and link to each other with
// relative URLs, so the URL layout here mirrors the cf26/ folder layout.
const CF26_DIR = path.join(__dirname, '../../cf26');
const PAGES = new Set(['gameplan.html', 'scouting_report.html']);
const OPPONENT_ID = /^[a-z0-9-]+$/;

const router = express.Router();

router.use(requireAdmin({ returnTo: true }));

router.use((req, res, next) => {
  // Behind a login: never cache in a shared cache (Cloudflare) or index.
  res.set('Cache-Control', 'private, no-store');
  res.set('X-Robots-Tag', 'noindex, nofollow');
  next();
});

function sendPage(res, next, ...parts) {
  const file = path.join(CF26_DIR, ...parts);
  if (!fs.existsSync(file)) return next();
  return res.sendFile(file);
}

router.get('/', (req, res, next) => {
  // The index links to "opponents/..." relatively, which only resolves under /cf26/ (with the slash).
  if (!req.originalUrl.split('?')[0].endsWith('/')) return res.redirect(301, '/cf26/');
  return sendPage(res, next, 'index.html');
});

router.get('/index.html', (req, res, next) => sendPage(res, next, 'index.html'));

router.get('/opponents/:opponent/reports/:page', (req, res, next) => {
  const { opponent, page } = req.params;
  if (!OPPONENT_ID.test(opponent) || !PAGES.has(page)) return next();
  return sendPage(res, next, 'opponents', opponent, 'reports', page);
});

module.exports = router;
