const crypto = require('crypto');
const express = require('express');
const multer = require('multer');
const { OAuth2Client } = require('google-auth-library');

const {
  createAdminToken, safeNextPath, TOKEN_COOKIE, STATE_COOKIE, NEXT_COOKIE, STATE_TTL_MS,
} = require('../lib/admin-auth');
const { requireAdmin } = require('../lib/require-admin');
const {
  resolveDataDir, listPhotos, addPhoto, updatePhotoAlt, deletePhoto,
} = require('../lib/gallery-store');
const { processUpload } = require('../lib/gallery-upload');

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });

const TOKEN_COOKIE_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

function secureCookies() {
  return process.env.NODE_ENV === 'production';
}

function oauthClient() {
  return new OAuth2Client({
    clientId: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    redirectUri: `${process.env.BASE_URL}/admin/auth/google/callback`,
  });
}

router.get('/login', (req, res) => {
  const next = safeNextPath(req.query.next);
  res.render('admin/login', {
    pageTitle: 'Admin Login',
    noIndex: true,
    nextParam: next ? encodeURIComponent(next) : null,
  });
});

router.get('/auth/google', (req, res) => {
  const state = crypto.randomBytes(16).toString('hex');
  res.cookie(STATE_COOKIE, state, {
    httpOnly: true, secure: secureCookies(), sameSite: 'lax', maxAge: STATE_TTL_MS,
  });

  // Remember where to go after login (e.g. a /cf26 page), for the length of the OAuth round trip.
  const next = safeNextPath(req.query.next);
  if (next) {
    res.cookie(NEXT_COOKIE, next, {
      httpOnly: true, secure: secureCookies(), sameSite: 'lax', maxAge: STATE_TTL_MS,
    });
  }

  const url = oauthClient().generateAuthUrl({ scope: ['email'], state });
  res.redirect(url);
});

router.get('/auth/google/callback', async (req, res) => {
  const { code, state } = req.query;
  const cookieState = req.cookies[STATE_COOKIE];
  const next = safeNextPath(req.cookies[NEXT_COOKIE]);
  res.clearCookie(STATE_COOKIE);
  res.clearCookie(NEXT_COOKIE);

  if (!state || !cookieState || state !== cookieState) {
    return res.status(403).render('error', {
      pageTitle: 'Login Failed',
      message: 'Invalid login state — please try signing in again.',
      noIndex: true,
    });
  }

  try {
    const client = oauthClient();
    const { tokens } = await client.getToken(String(code));
    const ticket = await client.verifyIdToken({ idToken: tokens.id_token, audience: process.env.GOOGLE_CLIENT_ID });
    const payload = ticket.getPayload();
    const adminEmail = process.env.ADMIN_EMAIL;

    if (!adminEmail || payload.email !== adminEmail) {
      return res.status(403).render('error', {
        pageTitle: 'Access Denied',
        message: 'This Google account is not authorized for admin access.',
        noIndex: true,
      });
    }

    const token = createAdminToken(payload.email, process.env.ADMIN_JWT_SECRET);
    res.cookie(TOKEN_COOKIE, token, {
      httpOnly: true, secure: secureCookies(), sameSite: 'lax', maxAge: TOKEN_COOKIE_MAX_AGE_MS,
    });
    return res.redirect(next || '/admin');
  } catch {
    return res.status(403).render('error', {
      pageTitle: 'Login Failed',
      message: 'Could not complete Google sign-in.',
      noIndex: true,
    });
  }
});

router.get('/logout', (req, res) => {
  res.clearCookie(TOKEN_COOKIE);
  res.redirect('/');
});

router.use(requireAdmin());

router.get('/', (req, res) => {
  const photos = listPhotos(resolveDataDir()).map((p) => ({
    ...p,
    thumb: `/img/gallery/thumb/${p.slug}.webp`,
    full: `/img/gallery/full/${p.slug}.webp`,
  }));

  res.render('admin/dashboard', {
    pageTitle: 'Admin',
    noIndex: true,
    adminEmail: req.adminEmail,
    photos,
    uploadError: req.query.uploadError,
  });
});

router.post('/photos', upload.single('photo'), async (req, res) => {
  if (!req.file) {
    return res.redirect('/admin?uploadError=No file was uploaded.');
  }

  try {
    const dataDir = resolveDataDir();
    const entry = addPhoto(dataDir, { source: req.file.originalname, alt: req.body.alt || '' });
    await processUpload(req.file.buffer, dataDir, entry.slug);
    return res.redirect('/admin');
  } catch {
    return res.redirect('/admin?uploadError=Could not process that image — try exporting it as a JPEG first.');
  }
});

router.post('/photos/:slug', (req, res) => {
  updatePhotoAlt(resolveDataDir(), req.params.slug, req.body.alt || '');
  res.redirect('/admin');
});

router.post('/photos/:slug/delete', (req, res) => {
  deletePhoto(resolveDataDir(), req.params.slug);
  res.redirect('/admin');
});

module.exports = router;
