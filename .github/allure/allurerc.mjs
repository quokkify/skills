export default {
  name: "Shared Agent Skills",
  output: "./allure-report",
  historyPath: "./allure-history/history.jsonl",
  historyLimit: 20,
  plugins: {
    awesome: {
      options: {
        reportName: "Shared Agent Skills test report",
        singleFile: false,
        reportLanguage: "en",
        groupBy: ["epic", "feature", "story"],
      },
    },
  },
};
