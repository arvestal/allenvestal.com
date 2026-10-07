const mockGenerateAuthUrl = jest.fn();
const mockGetToken = jest.fn();
const mockVerifyIdToken = jest.fn();

jest.mock('google-auth-library', () => ({
  OAuth2Client: jest.fn().mockImplementation(() => ({
    generateAuthUrl: mockGenerateAuthUrl,
    getToken: mockGetToken,
    verifyIdToken: mockVerifyIdToken,
  })),
}));

const fs = require('fs');
const os = require('os');
const path = require('path');
const sharp = require('sharp');
const request = require('supertest');
const { createAdminToken } = require('../src/lib/admin-auth');
const { writePhotos, listPhotos } = require('../src/lib/gallery-store');
const app = require('../src/app');

const ADMIN_EMAIL = 'arvestal@gmail.com';
const JWT_SECRET = 'test-jwt-secret';

function adminCookies() {
  return [`admin_token=${createAdminToken(ADMIN_EMAIL, JWT_SECRET)}`];
}

describe('GET /admin/login', () => {
  it('renders a sign-in link', async () => {
    const res = await request(app).get('/admin/login');
    expect(res.status).toBe(200);
    expect(res.text).toContain('href="/admin/auth/google"');
  });
});

describe('GET /admin/auth/google', () => {
  it('sets an oauth_state cookie and redirects to the generated Google URL', async () => {
    mockGenerateAuthUrl.mockReturnValue('https://accounts.google.com/o/oauth2/mock');
    const res = await request(app).get('/admin/auth/google');
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('https://accounts.google.com/o/oauth2/mock');
    expect(res.headers['set-cookie'].some((c) => c.startsWith('oauth_state='))).toBe(true);
  });
});

describe('GET /admin/auth/google/callback', () => {
  it('rejects when there is no state cookie at all', async () => {
    const res = await request(app).get('/admin/auth/google/callback?code=abc&state=xyz');
    expect(res.status).toBe(403);
    expect(res.text).toContain('Invalid login state');
  });

  it('rejects when the state query param does not match the state cookie', async () => {
    const res = await request(app)
      .get('/admin/auth/google/callback?code=abc&state=wrong')
      .set('Cookie', 'oauth_state=right');
    expect(res.status).toBe(403);
    expect(res.text).toContain('Invalid login state');
  });

  it('logs in and sets an admin_token cookie when the verified email matches ADMIN_EMAIL', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    mockGetToken.mockResolvedValue({ tokens: { id_token: 'fake-id-token' } });
    mockVerifyIdToken.mockResolvedValue({ getPayload: () => ({ email: ADMIN_EMAIL }) });

    const res = await request(app)
      .get('/admin/auth/google/callback?code=abc&state=match')
      .set('Cookie', 'oauth_state=match');

    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin');
    expect(res.headers['set-cookie'].some((c) => c.startsWith('admin_token='))).toBe(true);
  });

  it('denies access when the verified email does not match ADMIN_EMAIL', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    mockGetToken.mockResolvedValue({ tokens: { id_token: 'fake-id-token' } });
    mockVerifyIdToken.mockResolvedValue({ getPayload: () => ({ email: 'not-admin@gmail.com' }) });

    const res = await request(app)
      .get('/admin/auth/google/callback?code=abc&state=match')
      .set('Cookie', 'oauth_state=match');

    expect(res.status).toBe(403);
    expect(res.text).toContain('Access Denied');
  });

  it('shows a login-failed page when the Google token exchange throws', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    mockGetToken.mockRejectedValue(new Error('network error'));

    const res = await request(app)
      .get('/admin/auth/google/callback?code=abc&state=match')
      .set('Cookie', 'oauth_state=match');

    expect(res.status).toBe(403);
    expect(res.text).toContain('Could not complete Google sign-in');
  });
});

describe('returning to the requested page after login (?next=)', () => {
  it('carries a safe ?next= through the login page link', async () => {
    const res = await request(app).get('/admin/login?next=%2Fcf26%2F');
    expect(res.status).toBe(200);
    expect(res.text).toContain('href="/admin/auth/google?next=%2Fcf26%2F"');
  });

  it('drops an unsafe ?next= on the login page', async () => {
    const res = await request(app).get('/admin/login?next=%2F%2Fevil.com');
    expect(res.text).toContain('href="/admin/auth/google"');
    expect(res.text).not.toContain('evil.com');
  });

  it('remembers a safe ?next= in a short-lived cookie during the Google round trip', async () => {
    mockGenerateAuthUrl.mockReturnValue('https://accounts.google.com/o/oauth2/mock');
    const res = await request(app).get('/admin/auth/google?next=%2Fcf26%2F');
    expect(res.headers['set-cookie'].some((c) => c.startsWith('admin_next=%2Fcf26%2F'))).toBe(true);
  });

  it('does not set the cookie for an unsafe ?next=', async () => {
    mockGenerateAuthUrl.mockReturnValue('https://accounts.google.com/o/oauth2/mock');
    const res = await request(app).get('/admin/auth/google?next=https%3A%2F%2Fevil.com');
    expect(res.headers['set-cookie'].some((c) => c.startsWith('admin_next='))).toBe(false);
  });

  it('redirects to the remembered page after a successful login', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    mockGetToken.mockResolvedValue({ tokens: { id_token: 'fake-id-token' } });
    mockVerifyIdToken.mockResolvedValue({ getPayload: () => ({ email: ADMIN_EMAIL }) });

    const res = await request(app)
      .get('/admin/auth/google/callback?code=abc&state=match')
      .set('Cookie', ['oauth_state=match', 'admin_next=%2Fcf26%2Fopponents%2Fmike-iowa%2Freports%2Fgameplan.html']);

    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/cf26/opponents/mike-iowa/reports/gameplan.html');
  });
});

describe('GET /admin/logout', () => {
  it('clears the admin_token cookie and redirects home', async () => {
    const res = await request(app).get('/admin/logout');
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/');
    expect(res.headers['set-cookie'][0]).toMatch(/^admin_token=;/);
  });
});

describe('GET /admin', () => {
  const originalAdminEmail = process.env.ADMIN_EMAIL;
  const originalSecret = process.env.ADMIN_JWT_SECRET;

  afterEach(() => {
    process.env.ADMIN_EMAIL = originalAdminEmail;
    process.env.ADMIN_JWT_SECRET = originalSecret;
  });

  it('redirects to login when there is no admin_token cookie', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    const res = await request(app).get('/admin');
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin/login');
  });

  it('redirects to login when the admin_token cookie is invalid', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    const res = await request(app).get('/admin').set('Cookie', 'admin_token=garbage');
    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin/login');
  });

  it('renders the dashboard when the admin_token cookie is valid', async () => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    const token = createAdminToken(ADMIN_EMAIL, JWT_SECRET);

    const res = await request(app).get('/admin').set('Cookie', `admin_token=${token}`);
    expect(res.status).toBe(200);
    expect(res.text).toContain(ADMIN_EMAIL);
  });

  it('shows a 500 admin-not-configured page when ADMIN_EMAIL is unset', async () => {
    delete process.env.ADMIN_EMAIL;
    const res = await request(app).get('/admin');
    expect(res.status).toBe(500);
    expect(res.text).toContain('Admin Not Configured');
  });
});

describe('admin photo management', () => {
  const originalDataDir = process.env.GALLERY_DATA_DIR;
  let dataDir;

  beforeEach(() => {
    process.env.ADMIN_EMAIL = ADMIN_EMAIL;
    process.env.ADMIN_JWT_SECRET = JWT_SECRET;
    dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'admin-gallery-'));
    process.env.GALLERY_DATA_DIR = dataDir;
    writePhotos(dataDir, [
      { slug: 'tacoma-001', source: 'existing.jpg', alt: 'Existing photo', date: '2020-01-01T00:00:00.000Z' },
    ]);
  });

  afterAll(() => {
    if (originalDataDir === undefined) delete process.env.GALLERY_DATA_DIR;
    else process.env.GALLERY_DATA_DIR = originalDataDir;
  });

  it('lists existing photos on the dashboard', async () => {
    const res = await request(app).get('/admin').set('Cookie', adminCookies());
    expect(res.status).toBe(200);
    expect(res.text).toContain('/img/gallery/thumb/tacoma-001.webp');
    expect(res.text).toContain('Existing photo');
  });

  it('includes the full-size image URL for the admin preview modal', async () => {
    const res = await request(app).get('/admin').set('Cookie', adminCookies());
    expect(res.text).toContain('data-full="/img/gallery/full/tacoma-001.webp"');
  });

  it('uploads a new photo, converts it, and appends it to photos.json', async () => {
    const buffer = await sharp({
      create: {
        width: 600, height: 400, channels: 3, background: { r: 10, g: 20, b: 30 },
      },
    }).jpeg().toBuffer();

    const res = await request(app)
      .post('/admin/photos')
      .set('Cookie', adminCookies())
      .field('alt', 'A brand new photo')
      .attach('photo', buffer, 'new.jpg');

    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin');

    const photos = listPhotos(dataDir);
    expect(photos).toHaveLength(2);
    expect(photos[1]).toMatchObject({ slug: 'tacoma-002', source: 'new.jpg', alt: 'A brand new photo' });
    expect(fs.existsSync(path.join(dataDir, 'full/tacoma-002.webp'))).toBe(true);
    expect(fs.existsSync(path.join(dataDir, 'thumb/tacoma-002.webp'))).toBe(true);
  });

  it('redirects with an error when no file is uploaded', async () => {
    const res = await request(app).post('/admin/photos').set('Cookie', adminCookies());
    expect(res.status).toBe(302);
    expect(res.headers.location).toContain('uploadError=');
    expect(listPhotos(dataDir)).toHaveLength(1);
  });

  it('redirects with an error when the uploaded file cannot be decoded as an image', async () => {
    const res = await request(app)
      .post('/admin/photos')
      .set('Cookie', adminCookies())
      .attach('photo', Buffer.from('not an image'), 'broken.jpg');

    expect(res.status).toBe(302);
    expect(res.headers.location).toContain('uploadError=');
    expect(res.headers.location).toContain('JPEG');
  });

  it('updates alt text for an existing photo', async () => {
    const res = await request(app)
      .post('/admin/photos/tacoma-001')
      .set('Cookie', adminCookies())
      .send('alt=Updated alt text');

    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin');
    expect(listPhotos(dataDir)[0].alt).toBe('Updated alt text');
  });

  it('clears alt text to an empty string when the field is omitted', async () => {
    const res = await request(app)
      .post('/admin/photos/tacoma-001')
      .set('Cookie', adminCookies())
      .send({});

    expect(res.status).toBe(302);
    expect(listPhotos(dataDir)[0].alt).toBe('');
  });

  it('deletes a photo', async () => {
    const res = await request(app)
      .post('/admin/photos/tacoma-001/delete')
      .set('Cookie', adminCookies());

    expect(res.status).toBe(302);
    expect(res.headers.location).toBe('/admin');
    expect(listPhotos(dataDir)).toHaveLength(0);
  });
});
