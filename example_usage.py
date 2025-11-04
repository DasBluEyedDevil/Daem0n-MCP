"""
Example usage of DevilMCP Server
This demonstrates how to use the various capabilities of DevilMCP.
"""

import os
from pathlib import Path

# This is a demonstration script showing how an AI agent would use DevilMCP tools
# In practice, these tools would be called through the MCP protocol by the AI agent

def example_workflow():
    """
    Example workflow showing how to use DevilMCP effectively.
    """

    print("=" * 70)
    print("DevilMCP Example Usage Workflow")
    print("=" * 70)

    # ========================================================================
    # STEP 1: Start a Thought Session
    # ========================================================================
    print("\n📝 STEP 1: Starting a thought session...")

    session_info = {
        "session_id": "example-refactor-2024",
        "context": {
            "task": "Refactor authentication system",
            "project": "MyWebApp",
            "goal": "Improve security and scalability"
        }
    }

    print(f"Session ID: {session_info['session_id']}")
    print(f"Context: {session_info['context']}")

    # AI would call: start_thought_session(session_id, context)

    # ========================================================================
    # STEP 2: Analyze Project Structure
    # ========================================================================
    print("\n🔍 STEP 2: Analyzing project structure...")

    project_path = "/path/to/your/project"
    print(f"Analyzing: {project_path}")

    # AI would call: analyze_project_structure(project_path)
    # This would return:
    example_structure = {
        "root": project_path,
        "total_files": 150,
        "total_lines": 12500,
        "languages": ["Python", "JavaScript", "HTML", "CSS"],
        "file_types": {
            ".py": 45,
            ".js": 30,
            ".html": 15,
            ".css": 10
        }
    }

    print("Structure Analysis:")
    print(f"  - Total Files: {example_structure['total_files']}")
    print(f"  - Total Lines: {example_structure['total_lines']}")
    print(f"  - Languages: {', '.join(example_structure['languages'])}")

    # ========================================================================
    # STEP 3: Log Initial Thoughts
    # ========================================================================
    print("\n💭 STEP 3: Logging initial thoughts...")

    thoughts = [
        {
            "thought": "Current auth system uses sessions, causing scaling issues",
            "category": "analysis",
            "reasoning": "Session storage requires sticky sessions in load balancer",
            "confidence": 0.9
        },
        {
            "thought": "Could switch to JWT tokens for stateless auth",
            "category": "hypothesis",
            "reasoning": "JWTs are stateless and work well with horizontal scaling",
            "confidence": 0.8
        },
        {
            "thought": "Need to consider token refresh mechanism",
            "category": "concern",
            "reasoning": "Long-lived tokens are security risk; need refresh strategy",
            "confidence": 0.7
        }
    ]

    for i, thought in enumerate(thoughts, 1):
        print(f"\nThought {i}:")
        print(f"  Category: {thought['category']}")
        print(f"  Thought: {thought['thought']}")
        print(f"  Confidence: {thought['confidence']}")

    # AI would call: log_thought_process(...) for each thought

    # ========================================================================
    # STEP 4: Analyze Dependencies
    # ========================================================================
    print("\n🔗 STEP 4: Analyzing file dependencies...")

    target_file = "/path/to/auth/handler.py"
    print(f"Target file: {target_file}")

    # AI would call: track_file_dependencies(target_file, project_path)
    example_deps = {
        "file": target_file,
        "imports": ["jwt", "bcrypt", "database", "models.user"],
        "internal_deps": ["database", "models.user"],
        "external_deps": ["jwt", "bcrypt"]
    }

    print("Dependencies found:")
    print(f"  - Internal: {', '.join(example_deps['internal_deps'])}")
    print(f"  - External: {', '.join(example_deps['external_deps'])}")

    # ========================================================================
    # STEP 5: Analyze Change Impact
    # ========================================================================
    print("\n📊 STEP 5: Analyzing change impact...")

    change_desc = "Replace session-based auth with JWT tokens"

    # AI would call: analyze_change_impact(target_file, change_desc, example_deps)
    example_impact = {
        "file": target_file,
        "direct_impact": ["api/endpoints", "middleware/auth", "tests/auth"],
        "risk_factors": [
            "Change affects authentication - critical system component",
            "API changes may affect external consumers"
        ],
        "estimated_blast_radius": "high",
        "recommendations": [
            "Maintain API backward compatibility",
            "Implement comprehensive integration tests",
            "Plan gradual rollout with feature flag"
        ]
    }

    print("Impact Analysis:")
    print(f"  Blast Radius: {example_impact['estimated_blast_radius'].upper()}")
    print(f"  Direct Impact: {len(example_impact['direct_impact'])} components")
    print("\n  Risk Factors:")
    for risk in example_impact['risk_factors']:
        print(f"    ⚠️  {risk}")

    # ========================================================================
    # STEP 6: Analyze Cascade Risk
    # ========================================================================
    print("\n⚠️  STEP 6: Analyzing cascade failure risk...")

    # AI would call: analyze_cascade_risk(target_file, "modify", {...})
    cascade_risk = {
        "target": target_file,
        "cascade_probability": "high",
        "risk_level": "high",
        "affected_components": [
            "api/routes.py",
            "middleware/auth.py",
            "tests/test_auth.py",
            "api/users.py",
            "api/admin.py"
        ],
        "recommendations": [
            "⚠️  HIGH RISK: This change has high cascade potential",
            "Consider breaking this change into smaller, isolated changes",
            "Implement comprehensive integration tests before proceeding",
            "Set up canary deployment to catch issues early"
        ]
    }

    print(f"Cascade Risk Level: {cascade_risk['risk_level'].upper()}")
    print(f"Affected Components: {len(cascade_risk['affected_components'])}")
    print("\nRecommendations:")
    for rec in cascade_risk['recommendations'][:3]:
        print(f"  • {rec}")

    # ========================================================================
    # STEP 7: Check for Reasoning Gaps
    # ========================================================================
    print("\n🔍 STEP 7: Checking for reasoning gaps...")

    # AI would call: analyze_reasoning_gaps()
    gaps_analysis = {
        "total_thoughts": 3,
        "categories_covered": ["analysis", "hypothesis", "concern"],
        "gaps": [
            "No validation steps identified",
            "Risk assessment not performed"
        ],
        "suggestions": [
            "Define how to validate the approach",
            "Assess potential risks and mitigation strategies"
        ]
    }

    print("Reasoning Gap Analysis:")
    print(f"  Categories covered: {', '.join(gaps_analysis['categories_covered'])}")
    print("\n  Gaps identified:")
    for gap in gaps_analysis['gaps']:
        print(f"    ❌ {gap}")
    print("\n  Suggestions:")
    for suggestion in gaps_analysis['suggestions']:
        print(f"    💡 {suggestion}")

    # ========================================================================
    # STEP 8: Log the Decision
    # ========================================================================
    print("\n✅ STEP 8: Logging the decision...")

    decision = {
        "decision": "Implement JWT-based authentication with refresh tokens",
        "rationale": "Improves scalability by eliminating session state; "
                    "enhances security with short-lived tokens",
        "alternatives_considered": [
            "Keep session-based auth with Redis",
            "Use OAuth2 with external provider",
            "Implement API keys only"
        ],
        "expected_impact": "Enables horizontal scaling; reduces server memory usage; "
                          "improves security posture",
        "risk_level": "high",
        "tags": ["authentication", "security", "scalability", "refactor"]
    }

    print(f"Decision: {decision['decision']}")
    print(f"Risk Level: {decision['risk_level']}")
    print(f"Alternatives considered: {len(decision['alternatives_considered'])}")

    # AI would call: log_decision(...)

    # ========================================================================
    # STEP 9: Get Safe Change Suggestions
    # ========================================================================
    print("\n💡 STEP 9: Getting safe change suggestions...")

    # AI would call: suggest_safe_changes(target_file, change_desc)
    safe_suggestions = {
        "approach": [
            "Use adapter pattern to maintain backward compatibility",
            "Implement changes behind feature flag",
            "Add extensive logging and monitoring"
        ],
        "testing_strategy": [
            "Comprehensive integration test suite",
            "Test with production-like data volume",
            "Stress testing of affected components"
        ],
        "rollout_plan": [
            "Stage 1: Deploy to development environment",
            "Stage 2: Limited rollout to 5% of traffic",
            "Stage 3: Monitor metrics for 24-48 hours",
            "Stage 4: Gradual increase if metrics are good"
        ]
    }

    print("\nSafe Implementation Approach:")
    for item in safe_suggestions['approach']:
        print(f"  • {item}")

    print("\nTesting Strategy:")
    for item in safe_suggestions['testing_strategy']:
        print(f"  • {item}")

    # ========================================================================
    # STEP 10: Log the Change
    # ========================================================================
    print("\n📝 STEP 10: Logging the change...")

    change_record = {
        "file_path": target_file,
        "change_type": "refactor",
        "description": "Refactor authentication to use JWT tokens",
        "affected_components": cascade_risk['affected_components'],
        "rollback_plan": "Feature flag allows instant rollback to old auth; "
                        "keep old code for 30 days"
    }

    print(f"Change Type: {change_record['change_type']}")
    print(f"Affected Components: {len(change_record['affected_components'])}")
    print(f"Rollback Plan: {change_record['rollback_plan'][:50]}...")

    # AI would call: log_change(...)

    # ========================================================================
    # STEP 11: Record Insights
    # ========================================================================
    print("\n💎 STEP 11: Recording insights...")

    insights = [
        {
            "insight": "Authentication changes always have wide blast radius",
            "source": "Cascade analysis of auth handler",
            "applicability": "Always use feature flags for auth changes"
        },
        {
            "insight": "JWT refresh strategy is critical for security",
            "source": "Security review during planning",
            "applicability": "Include refresh mechanism in all token-based auth"
        }
    ]

    for i, insight in enumerate(insights, 1):
        print(f"\nInsight {i}: {insight['insight']}")
        print(f"  Application: {insight['applicability']}")

    # AI would call: record_insight(...) for each

    # ========================================================================
    # STEP 12: End Session
    # ========================================================================
    print("\n🏁 STEP 12: Ending thought session...")

    session_summary = {
        "summary": "Planned JWT authentication refactor with comprehensive "
                  "risk analysis and mitigation strategies",
        "outcomes": [
            "Identified high cascade risk",
            "Developed safe rollout plan",
            "Documented rollback procedures",
            "Recorded key insights for future"
        ]
    }

    print(f"Summary: {session_summary['summary']}")
    print(f"Outcomes: {len(session_summary['outcomes'])} achieved")

    # AI would call: end_thought_session(session_id, summary, outcomes)

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("Workflow Complete!")
    print("=" * 70)
    print("""
This example demonstrates how DevilMCP helps AI agents:
  ✓ Maintain full context throughout the work session
  ✓ Track their reasoning and check for gaps
  ✓ Understand change impacts before making changes
  ✓ Detect cascade failure risks
  ✓ Make informed decisions with full rationale
  ✓ Learn from experience through insights

Result: AI agents make better decisions and avoid short-sighted changes
that could cause cascading failures.
    """)


if __name__ == "__main__":
    example_workflow()
