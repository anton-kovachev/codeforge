import unittest

from output_models.debug_code import DebuggedCodeOutput


class DebuggedCodeOutputTest(unittest.TestCase):
    def test_updated_tests_is_optional(self):
        output = DebuggedCodeOutput(
            code="print(1)",
            tests="assert 1 == 1",
            description="No changes needed.",
        )

        self.assertIsNone(output.updated_tests)

    def test_updated_tests_is_preserved(self):
        output = DebuggedCodeOutput(
            code="print(1)",
            tests="assert 1 == 1",
            updated_tests="assert print(1) is None",
            description="Updated the tests.",
        )

        self.assertEqual(output.updated_tests, "assert print(1) is None")


if __name__ == "__main__":
    unittest.main()
