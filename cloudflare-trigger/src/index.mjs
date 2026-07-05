export function modeForCron(cron) {
  if (cron === "20 1 * * *" || cron === "47 1 * * *") return "production";
  if (cron === "5 2 * * *") return "watchdog";
  throw new Error(`Unsupported cron: ${cron}`);
}


export async function dispatch(env, mode, fetchImpl = fetch) {
  const response = await fetchImpl(
    `https://api.github.com/repos/${env.REPO}/actions/workflows/daily-report.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "canyin-ai-news-scheduler",
      },
      body: JSON.stringify({
        ref: "main",
        inputs: { mode },
      }),
    },
  );
  if (response.status !== 204) {
    throw new Error(`GitHub dispatch failed: ${response.status}`);
  }
}


export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(dispatch(env, modeForCron(controller.cron)));
  },
};
