import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      "react/prop-types": "off",
      "react-refresh/only-export-components": "warn",
    },
    settings: { react: { version: "detect" } },
  },
  {
    files: ["*.config.js"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
  {
    // R3F uses Three.js props (args, position, castShadow, …) that are not DOM attributes.
    files: ["src/pages/ghostwalk/GhostwalkScene.jsx"],
    rules: {
      "react/no-unknown-property": "off",
    },
  },
];
