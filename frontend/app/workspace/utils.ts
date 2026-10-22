import type { DebuggedCodeResult, TodoItem } from "./models";

export const languageOptions = [
  { value: "python", label: "Python", monacoLanguage: "python" },
  {
    value: "typescript",
    label: "TypeScript",
    monacoLanguage: "typescript",
  },
  { value: "solidity", label: "Solidity", monacoLanguage: "sol" },
  { value: "go", label: "Go", monacoLanguage: "go" },
  { value: "rust", label: "Rust", monacoLanguage: "rust" },
] as const;

export type LanguageOption = (typeof languageOptions)[number];

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isTodoItem(value: unknown): value is TodoItem {
  return (
    isRecord(value) &&
    typeof value.description === "string" &&
    typeof value.completed === "boolean" &&
    typeof value.order === "number"
  );
}

export function isDebuggedCodeResult(
  value: unknown,
): value is DebuggedCodeResult {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    (typeof value.updated_code === "string" ||
      value.updated_code === null ||
      value.updated_code === undefined) &&
    typeof value.tests === "string" &&
    (typeof value.updated_tests === "string" ||
      value.updated_tests === null ||
      value.updated_tests === undefined) &&
    typeof value.description === "string"
  );
}
