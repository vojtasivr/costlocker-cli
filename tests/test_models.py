from __future__ import annotations

from costlocker_cli.models import Project


class TestProjectDisplayName:
    def test_without_subtask(self):
        project = Project(budget_id=1, budget_name="Acme Corp", activity_id=10, activity_name="Development")
        assert project.display_name == "Acme Corp - Development"

    def test_with_subtask(self):
        project = Project(
            budget_id=1,
            budget_name="Acme Corp",
            activity_id=10,
            activity_name="Development",
            subtask_id=100,
            subtask_name="Backend",
        )
        assert project.display_name == "Acme Corp - Development - Backend"

    def test_subtask_id_without_name_omitted(self):
        # subtask_name=None should not append anything even if subtask_id is set
        project = Project(
            budget_id=1, budget_name="Proj", activity_id=2, activity_name="Act", subtask_id=99, subtask_name=None
        )
        assert project.display_name == "Proj - Act"
