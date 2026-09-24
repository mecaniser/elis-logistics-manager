# Account sign-in and recovery

The existing `APP_AUTH_USERNAME` and `APP_AUTH_PASSWORD` continue to bootstrap the single account. The first successful password reset stores a salted scrypt hash in `auth_account`; from then on, the environment password no longer signs in. The API still enforces authentication if the environment password is removed after a reset. Keep `APP_AUTH_USERNAME` and `APP_AUTH_SECRET` stable and backed up: the secret signs sessions and encrypts authenticator secrets.

The default session lasts 12 hours. Selecting **Keep me signed in** creates an HTTP-only cookie lasting up to seven days, including across browser restarts. Set `APP_AUTH_COOKIE_SECURE=true` on HTTPS. Changing the account password or enabling MFA invalidates earlier cookies.

To activate self-service password recovery, configure a distinct `APP_AUTH_SECRET`, `APP_AUTH_RECOVERY_EMAIL`, an HTTPS origin in `APP_PUBLIC_URL`, `APP_SMTP_HOST`, `APP_SMTP_FROM`, and SMTP credentials/port as needed. Verify the address and sender before enabling this in production. The recovery screen explains when delivery is not configured. Reset links expire after 20 minutes and can be used once. A completed reset does not bypass MFA.

The account menu has **Account security**. The signed-in owner confirms their password, adds the displayed key to an authenticator app, and confirms a six-digit code. Save the eight recovery codes shown after enrollment. Each works once. If both authenticator and codes are lost, recovery requires an administrator with deployment and database access; an email password reset alone does not disable MFA.

Deploy with the new `auth_account` migration and `cryptography` dependency before using these screens. Do not put reset tokens, authenticator secrets, or recovery codes in logs or browser storage.
