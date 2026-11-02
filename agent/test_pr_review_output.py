import unittest

from output_models.pr_review import PRReviewFinding, PRReviewOutput
from review_tools import create_pr_review_todo_tools


class PRReviewOutputTest(unittest.TestCase):
    def test_findings_default_to_empty_and_verdict_is_required(self):
        output = PRReviewOutput(summary="No issues found.", verdict=True)

        self.assertEqual(output.findings, [])
        with self.assertRaises(ValueError):
            PRReviewOutput(summary="Missing verdict")

    def test_finding_accepts_optional_tests(self):
        finding = PRReviewFinding(
            file_path="src/calculator.py",
            code="return total",
            new_code="return total / count",
            comment="The result is not averaged.",
            severity="P2",
        )

        self.assertEqual(finding.file_path, "src/calculator.py")
        self.assertIsNone(finding.tests)

    def test_finding_requires_code_fix_and_explanation(self):
        with self.assertRaises(ValueError):
            PRReviewFinding(
                code="return total",
                new_code="return total / count",
                comment="The result is not averaged.",
                severity="P2",
            )

    def test_finding_requires_file_path(self):
        with self.assertRaises(ValueError):
            PRReviewFinding(
                code="return total",
                new_code="return total / count",
                comment="The result is not averaged.",
                severity="P2",
            )

    def test_finding_rejects_non_repository_relative_file_paths(self):
        for file_path in ("/src/file.py", "../src/file.py", "src\\file.py"):
            with self.subTest(file_path=file_path), self.assertRaises(ValueError):
                PRReviewFinding(
                    file_path=file_path,
                    code="return total",
                    new_code="return total / count",
                    comment="The result is not averaged.",
                    severity="P2",
                )

    def test_review_todo_tools_have_distinct_names(self):
        tools = create_pr_review_todo_tools()

        self.assertEqual(
            {tool.tool_name for tool in tools},
            {
                "create_pr_review_todos",
                "mark_complete_pr_review_todo",
                "list_pr_review_todos",
            },
        )


if __name__ == "__main__":
    unittest.main()
