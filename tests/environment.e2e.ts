export const ENV = {
  // Ruin against local backend
  apiUrl: 'http://0.0.0.0:8000/api/v1/',

  // Compile as production
  production: true,

  // No need for incomplete features during E2E tests
  ffEnableIncomplete: false,

  // No Sentry reporting for E2E tests
  sentryDsn: undefined
};
