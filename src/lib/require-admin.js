const { verifyAdminToken, TOKEN_COOKIE } = require('./admin-auth');

// Express middleware: lets the request through only with a valid admin session cookie for
// ADMIN_EMAIL. Shared by /admin and the private /cf26 scouting pages.
// With { returnTo: true }, an unauthenticated visitor is sent to the login page with ?next= set to
// the page they asked for, so they land back on it after signing in.
function requireAdmin({ returnTo = false } = {}) {
  return (req, res, next) => {
    const adminEmail = process.env.ADMIN_EMAIL;
    if (!adminEmail) {
      return res.status(500).render('error', {
        pageTitle: 'Admin Not Configured',
        message: 'ADMIN_EMAIL is not set for this deployment.',
        noIndex: true,
      });
    }

    const payload = verifyAdminToken(req.cookies[TOKEN_COOKIE], process.env.ADMIN_JWT_SECRET, adminEmail);
    if (!payload) {
      return res.redirect(returnTo ? `/admin/login?next=${encodeURIComponent(req.originalUrl)}` : '/admin/login');
    }

    req.adminEmail = payload.email;
    return next();
  };
}

module.exports = { requireAdmin };
