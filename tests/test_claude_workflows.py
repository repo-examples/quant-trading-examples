from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_claude_interactive_workflow_contract() -> None:
    claude_yml = REPO_ROOT / ".github" / "workflows" / "claude.yml"
    assert claude_yml.exists(), ".github/workflows/claude.yml must exist"
    content = claude_yml.read_text(encoding="utf-8")
    assert "name: Claude Code" in content
    assert "anthropics/claude-code-action@v1" in content
    assert "CLAUDE_CODE_OAUTH_TOKEN" in content
    assert "--model claude-opus-5-5 --effort high" in content


def test_pr_review_and_ci_workflow_contract() -> None:
    pr_review_yml = REPO_ROOT / ".github" / "workflows" / "pr-review.yml"
    prompt_md = REPO_ROOT / ".github" / "workflows" / "prompts" / "pr-review.md"
    ci_yml = REPO_ROOT / ".github" / "workflows" / "ci.yml"

    assert pr_review_yml.exists(), ".github/workflows/pr-review.yml must exist"
    assert prompt_md.exists(), ".github/workflows/prompts/pr-review.md must exist"
    assert ci_yml.exists(), ".github/workflows/ci.yml must exist"

    ci_text = ci_yml.read_text(encoding="utf-8")
    assert "name: CI" in ci_text
    assert "ruff check src tests" in ci_text
    assert "pytest -v" in ci_text
    assert "quantlab dashboard --check" in ci_text

    review_text = pr_review_yml.read_text(encoding="utf-8")
    assert "name: PR Review" in review_text
    assert "ROUND_CAP: 3" in review_text
    assert 'VERDICT_MARKER: "<!-- pr-review-verdict -->"' in review_text
    assert 'CI_WORKFLOW_NAME: "CI"' in review_text
    assert "[skip pr-review]" in review_text
    assert "anthropics/claude-code-action@v1" in review_text

    prompt_text = prompt_md.read_text(encoding="utf-8")
    assert "repo-examples/quant-trading-examples" in prompt_text
    assert "pr_review_output.json" in prompt_text
    assert "APPROVED" in prompt_text
    assert "CHANGES_REQUESTED" in prompt_text
