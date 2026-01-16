"""Report generator for auto-fix results."""

from html import escape
from pathlib import Path
from .models import AutoFixReport


class ReportGenerator:
    """Generates markdown reports from AutoFixReport."""

    def generate_report(self, report: AutoFixReport) -> str:
        """Generate full markdown report.

        Args:
            report: The AutoFixReport object

        Returns:
            Markdown content
        """
        lines = [
            f"# Auto-Fix Report: {report.story_key}",
            "",
            "## Summary",
            f"- **Total Issues:** {report.total_issues}",
            f"- **Fixed:** {report.fixed_count}",
            f"- **Failed:** {report.failed_count}",
            f"- **Skipped:** {report.skipped_count}",
            f"- **Success Rate:** {report.fix_rate:.1%}",
            "",
            "## Fix Details",
            ""
        ]

        if not report.results:
            lines.append("_No issues processed._")
            return "\n".join(lines)

        for result in report.results:
            icon = "✅" if result.status == "success" else "❌" if result.status == "failed" else "⚠️"
            status = result.status.upper()
            
            # Escape problem to prevent markdown injection (LOW-9)
            safe_problem = escape(result.issue.problem)
            lines.append(f"### {icon} {status}: {safe_problem}")
            lines.append(f"**File:** `{result.issue.file}`")
            lines.append(f"**Severity:** {result.issue.severity}")
            
            if result.error_message:
                lines.append(f"**Error:** `{result.error_message}`")
            
            if result.changes:
                lines.append("**Changes:**")
                for change in result.changes:
                    lines.append(f"- {change}")
            
            lines.append("---")

        lines.append("")
        lines.append("## Remaining Manual Issues")
        manual_issues = [r for r in report.results if r.status != "success"]
        
        if not manual_issues:
            lines.append("All identified issues were resolved.")
        else:
            for r in manual_issues:
                lines.append(f"- [{r.issue.severity}] {r.issue.problem} ({r.issue.file})")

        return "\n".join(lines)

    def save_report(self, report: AutoFixReport, output_dir: Path) -> Path:
        """Generate and save report to file.

        Args:
            report: The report object
            output_dir: Directory to save report

        Returns:
            Path to saved report
        """
        content = self.generate_report(report)
        report_file = output_dir / "auto-fix-report.md"
        report_file.write_text(content)
        return report_file
