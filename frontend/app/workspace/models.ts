export type TodoItem = {
  description: string;
  completed: boolean;
  order: number;
};

export type DebuggedCodeResult = {
  code: string;
  updated_code?: string | null;
  tests: string;
  updated_tests?: string | null;
  description: string;
};
