import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from input_guardrail import (
    CodeInputRejected,
    extract_code_input,
    validate_code_input,
)


class InputGuardrailTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = AsyncMock()
        self.client.__aenter__.return_value = self.client
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {"is_valid": True, "reason": "Looks like Python."}
                        )
                    )
                )
            ]
        )
        self.openai_patcher = patch(
            "input_guardrail.AsyncOpenAI", return_value=self.client
        )
        self.token_patcher = patch(
            "input_guardrail.provide_token", return_value="test"
        )
        self.openai_patcher.start()
        self.token_patcher.start()
        self.addCleanup(self.openai_patcher.stop)
        self.addCleanup(self.token_patcher.stop)

    async def test_accepts_plausible_code(self):
        await validate_code_input("def add(a, b): return a + b", "python")
        self.client.chat.completions.create.assert_awaited_once()

    async def test_rejects_non_code(self):
        self.client.chat.completions.create.return_value.choices[0].message.content = (
            json.dumps({"is_valid": False, "reason": "This is ordinary prose."})
        )

        with self.assertRaisesRegex(CodeInputRejected, "ordinary prose"):
            await validate_code_input("Hello, how are you?", "python")

    async def test_rejects_empty_code_without_calling_model(self):
        with self.assertRaisesRegex(CodeInputRejected, "cannot be empty"):
            await validate_code_input(" \n ", "python")

        self.client.chat.completions.create.assert_not_awaited()

    def test_extracts_code_and_language_from_legacy_prompt(self):
        code, language = extract_code_input(
            "Review this:\n\n```typescript\nconst answer: number = 42;\n```"
        )

        self.assertEqual(language, "typescript")
        self.assertEqual(code, "const answer: number = 42;")

    def test_requires_language_labeled_code_block_for_legacy_prompt(self):
        with self.assertRaises(CodeInputRejected):
            extract_code_input("Please debug my code.")


if __name__ == "__main__":
    unittest.main()
