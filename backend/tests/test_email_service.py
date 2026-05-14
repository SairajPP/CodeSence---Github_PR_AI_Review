import pytest
from models.schemas import PREvent, ReviewResult, AgentFinding, Severity, AgentType, ReviewAction
from services.email_service import _generate_html_body, send_review_email

@pytest.fixture
def sample_pr_event():
    return PREvent(
        action="opened",
        pr_number=42,
        pr_title="Add new feature X",
        repo_full_name="user/repo",
        repo_owner="user",
        repo_name="repo",
        diff_url="https://github.com/user/repo/pull/42.diff",
        sender="developer"
    )

@pytest.fixture
def sample_review():
    finding = AgentFinding(
        file="src/main.py",
        line=10,
        severity=Severity.CRITICAL,
        agent=AgentType.SECURITY,
        title="SQL Injection",
        explanation="Direct user input used in query.",
        suggestion="Use parameterized queries."
    )
    return ReviewResult(
        pr_number=42,
        repo_full_name="user/repo",
        summary="This PR has critical security issues.",
        findings=[finding],
        total_critical=1,
        total_warnings=0,
        total_info=0,
        review_action=ReviewAction.REQUEST_CHANGES
    )

def test_generate_html_body(sample_pr_event, sample_review):
    """Test that the HTML body is generated correctly with PR and Review details."""
    html = _generate_html_body(sample_pr_event, sample_review)
    
    # Check PR details
    assert "Your Pull Request <strong>#42 (Add new feature X)</strong>" in html
    assert "user/repo" in html
    
    # Check Review summary
    assert "This PR has critical security issues." in html
    
    # Check Breakdown
    assert "🔴 <strong>Critical:</strong> 1" in html
    assert "🟡 <strong>Warning:</strong> 0" in html
    
    # Check Findings
    assert "SQL Injection" in html
    assert "<code>src/main.py:10</code>" in html
    assert "Direct user input used in query." in html

def test_generate_html_body_no_findings(sample_pr_event):
    """Test HTML body generation when there are no findings."""
    perfect_review = ReviewResult(
        pr_number=42,
        repo_full_name="user/repo",
        summary="Looks great!",
        findings=[],
        total_critical=0,
        total_warnings=0,
        total_info=0,
        review_action=ReviewAction.APPROVE
    )
    html = _generate_html_body(sample_pr_event, perfect_review)
    
    assert "Looks great!" in html
    assert "No issues found! Great job." in html

def test_send_review_email_mock(sample_pr_event, sample_review, capsys):
    """Test that sending email falls back to printing when no SMTP credentials are provided."""
    # Ensure no SMTP credentials (should default to mock)
    # Using capsys to capture the print statement
    result = send_review_email(sample_pr_event, sample_review, "test@example.com")
    
    assert result is True
    captured = capsys.readouterr()
    assert "[MOCK EMAIL]" in captured.out
    assert "To: test@example.com" in captured.out
    assert "Subject: [CodeSense] Review Completed: PR #42 - Add new feature X" in captured.out
