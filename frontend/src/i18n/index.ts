import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import commonKo from "./ko/common.json";
import loginKo from "./ko/login.json";
import registerKo from "./ko/register.json";
import headerKo from "./ko/header.json";
import projectKo from "./ko/project.json";
import testcaseKo from "./ko/testcase.json";
import testrunKo from "./ko/testrun.json";
import dashboardKo from "./ko/dashboard.json";
import settingsKo from "./ko/settings.json";
import reportKo from "./ko/report.json";
import compareKo from "./ko/compare.json";
import adminKo from "./ko/admin.json";
import manualKo from "./ko/manual.json";
import adminManualKo from "./ko/adminManual.json";

import commonEn from "./en/common.json";
import loginEn from "./en/login.json";
import registerEn from "./en/register.json";
import headerEn from "./en/header.json";
import projectEn from "./en/project.json";
import testcaseEn from "./en/testcase.json";
import testrunEn from "./en/testrun.json";
import dashboardEn from "./en/dashboard.json";
import settingsEn from "./en/settings.json";
import reportEn from "./en/report.json";
import compareEn from "./en/compare.json";
import adminEn from "./en/admin.json";
import manualEn from "./en/manual.json";
import adminManualEn from "./en/adminManual.json";

i18n.use(initReactI18next).init({
  lng: localStorage.getItem("lang") || "ko",
  fallbackLng: "ko",
  defaultNS: "common",
  interpolation: {
    escapeValue: false,
  },
  resources: {
    ko: {
      common: commonKo,
      login: loginKo,
      register: registerKo,
      header: headerKo,
      project: projectKo,
      testcase: testcaseKo,
      testrun: testrunKo,
      dashboard: dashboardKo,
      settings: settingsKo,
      report: reportKo,
      compare: compareKo,
      admin: adminKo,
      manual: manualKo,
      adminManual: adminManualKo,
    },
    en: {
      common: commonEn,
      login: loginEn,
      register: registerEn,
      header: headerEn,
      project: projectEn,
      testcase: testcaseEn,
      testrun: testrunEn,
      dashboard: dashboardEn,
      settings: settingsEn,
      report: reportEn,
      compare: compareEn,
      admin: adminEn,
      manual: manualEn,
      adminManual: adminManualEn,
    },
  },
});

export default i18n;
