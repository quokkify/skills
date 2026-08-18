export default {
  name: "Shared Agent Skills",
  output: "./allure-report",
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
