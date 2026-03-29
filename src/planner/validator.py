"""
Plan Validator — pre-execution validation to catch bad plans before they run.

Checks every step against the tool registry and detects structural issues.
"""

from core.types import StepPlan
from tools.registry import ToolRegistry


class PlanValidator:
    """
    Validates a plan before the executor runs it.
    Catches issues the planner might produce (wrong tools, bad args, circular deps).
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def validate(self, steps: list[StepPlan]) -> dict:
        """
        Validate a complete plan.
        
        Returns:
            {
                "valid": True/False,
                "issues": [{"step_id": int, "error": str, "fixable": bool}],
                "warnings": [str],
            }
        """
        issues = []
        warnings = []
        step_ids = {s.id for s in steps}

        for step in steps:
            # 1. Tool exists?
            if not self.registry.has(step.tool):
                available = ", ".join(self.registry.list_names())
                issues.append({
                    "step_id": step.id,
                    "error": f"Tool '{step.tool}' not found. Available: [{available}]",
                    "fixable": True,
                })
                continue

            # 2. Action valid?
            tool = self.registry.get(step.tool)
            if step.action not in tool.actions:
                issues.append({
                    "step_id": step.id,
                    "error": f"Tool '{step.tool}' doesn't support '{step.action}'. Valid: {tool.actions}",
                    "fixable": True,
                })
                continue

            # 3. Tool-specific arg validation
            is_valid, error = tool.validate(step.action, step.args)
            if not is_valid:
                issues.append({
                    "step_id": step.id,
                    "error": error,
                    "fixable": True,
                })

            # 4. Dependencies exist?
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    issues.append({
                        "step_id": step.id,
                        "error": f"Depends on step {dep_id} which doesn't exist in the plan",
                        "fixable": True,
                    })

            # 5. No circular dependencies
            if step.id in step.depends_on:
                issues.append({
                    "step_id": step.id,
                    "error": "Step depends on itself (circular dependency)",
                    "fixable": True,
                })

            # 6. No forward dependencies (step depends on later step)
            for dep_id in step.depends_on:
                if dep_id >= step.id:
                    issues.append({
                        "step_id": step.id,
                        "error": f"Step {step.id} depends on later step {dep_id} (forward dependency)",
                        "fixable": True,
                    })

        # Warnings
        if len(steps) > 10:
            warnings.append(f"Plan has {len(steps)} steps — consider simplifying")

        duplicate_ids = len(step_ids) < len(steps)
        if duplicate_ids:
            warnings.append("Plan contains duplicate step IDs")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def format_issues(self, validation: dict) -> str:
        """Format validation issues as a readable string for the planner."""
        if validation["valid"]:
            return "Plan is valid ✅"

        lines = ["Plan validation FAILED:\n"]
        for issue in validation["issues"]:
            fixable = "🔧" if issue["fixable"] else "❌"
            lines.append(f"  {fixable} Step {issue['step_id']}: {issue['error']}")

        for warning in validation.get("warnings", []):
            lines.append(f"  ⚠️ {warning}")

        return "\n".join(lines)
