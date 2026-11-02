from strands import tool

from tools import ToDoItem, ToDoReport


def create_pr_review_todo_tools():
    todos: list[ToDoItem] = []

    def report_todos() -> ToDoReport:
        report = ""
        for index, todo in enumerate(todos, start=1):
            completed = "X" if todo.completed else " "
            report += f"Todo #{index}: [{completed}] {todo.description}\n"
        return ToDoReport(todos=list(todos), report=report)

    @tool
    def create_pr_review_todos(descriptions: list[str]) -> ToDoReport:
        """Create the ordered plan for reviewing the pull request."""
        for description in descriptions:
            todos.append(
                ToDoItem(
                    description=description,
                    completed=False,
                    order=len(todos) + 1,
                )
            )
        return report_todos()

    @tool
    def mark_complete_pr_review_todo(index: int) -> ToDoReport:
        """Mark the PR review todo at the given one-based index as complete."""
        if 1 <= index <= len(todos):
            todos[index - 1].completed = True
        return report_todos()

    @tool
    def list_pr_review_todos() -> ToDoReport:
        """Return the PR review todo list and completion states."""
        return report_todos()

    return [
        create_pr_review_todos,
        mark_complete_pr_review_todo,
        list_pr_review_todos,
    ]
