import base from './demo.config.mjs';

// Marks the page when the recording starts after login, so a scenario can check the order.
export default {
  ...base,
  async login(page, ctx) {
    await base.login(page, ctx);
    const start = page.screencast.start.bind(page.screencast);
    page.screencast.start = (options) => {
      page.recordingStartedAfterLogin = true;
      return start(options);
    };
  },
};
