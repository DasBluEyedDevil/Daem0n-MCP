# DevilMCP Real-World Scenarios

Practical examples showing how to use DevilMCP in common development situations.

---

## Scenario 1: "Should I Use Redux or Context API?"

### The Situation
You're building a React app and need to decide on state management.

### How Claude Code + DevilMCP Helps

**You ask:** "Should I use Redux or Context API for state management?"

**Claude responds:**

```
Let me help you make an informed decision. First, let me check if
we've made similar decisions before...

[Uses query_decisions(query="state management", tags=["react"])]

Found 0 past decisions about React state management.

Let me log this decision with full analysis:

[Uses log_decision(
    decision="Use Context API for state management",
    rationale="Small-medium app (estimated <20 components needing state),
              no complex middleware needed, team is small (2 devs),
              simpler learning curve, built into React",
    context={
        "project": "E-commerce Dashboard",
        "app_size": "medium",
        "team_size": 2,
        "complexity": "moderate",
        "timeline": "3 months"
    },
    alternatives_considered=[
        "Redux - Overkill for this app size, adds complexity",
        "MobX - Good but team not familiar with it",
        "Zustand - Simpler but less documentation",
        "Plain useState - Won't scale well"
    ],
    expected_impact="Faster development, easier testing, less boilerplate",
    risk_level="low",
    tags=["react", "state-management", "architecture"]
)]

Decision logged as #1.

Recommendation: Context API
Reasons:
- Your app has ~15 components that need shared state
- No complex async operations requiring middleware
- Team is small and familiar with Context API
- Can always migrate to Redux later if needed

Would you like me to help implement it?
```

**Later, after implementation:**

**You say:** "Context API is working great! Much simpler than I expected."

```
[Uses update_decision_outcome(
    decision_id=1,
    outcome="Successfully implemented Context API. Took 2 days.",
    actual_impact="Development velocity increased. Team happy with simplicity.
                  Zero state management bugs so far.",
    lessons_learned="Context API perfect for this scale. Splitting contexts
                    by feature worked well."
)]

Excellent! I've recorded the successful outcome for future reference.
```

---

## Scenario 2: "I Need to Change the Database Schema"

### The Situation
You need to rename the `User.email` field to `User.email_address` for consistency.

### How DevilMCP Prevents Disaster

**You ask:** "I want to rename the email field in the User model to email_address"

**Claude responds:**

```
⚠️  IMPORTANT: Let me analyze the impact of this change before proceeding.

[Uses track_file_dependencies(
    file_path="src/models/user.py"
)]

Found that user.py is imported by 8 files.

[Uses analyze_change_impact(
    file_path="src/models/user.py",
    change_description="Rename User.email to User.email_address",
    dependencies={
        "imported_by": [
            "src/api/user_routes.py",
            "src/api/auth_routes.py",
            "src/services/email_service.py",
            "src/services/notification_service.py",
            "src/middleware/auth.py",
            "tests/test_users.py",
            "tests/test_auth.py",
            "tasks/send_newsletters.py"
        ]
    }
)]

🚨 HIGH IMPACT CHANGE DETECTED:

Affected files: 8
Risk level: HIGH
Impact assessment:
  - Database migration required
  - 8 files need updates
  - Authentication system affected
  - Email service affected
  - All tests need updates

Specific issues:
  1. user_routes.py: Uses user.email in 3 endpoints
  2. auth_routes.py: Queries by email field
  3. email_service.py: Accesses user.email directly
  4. auth.py middleware: Validates email format
  5. Tests: All assertions on .email will fail

[Uses analyze_cascade_risk(
    target="src/models/user.py",
    change_type="breaking"
)]

CASCADE RISK: HIGH (75%)

Potential cascade chain:
  user.py → auth_routes.py → API endpoints → Frontend
  user.py → email_service.py → Newsletter system
  user.py → auth.py → All authenticated routes

Recommendations:
1. Create database migration with both old and new columns
2. Add property alias: @property email() -> self.email_address
3. Update files one by one with testing
4. Deprecation period before removing alias
5. Deploy in stages with feature flag

Would you like me to:
A) Create a safe migration plan
B) Proceed with the risky direct rename
C) Consider alternatives

I recommend option A to avoid breaking production.
```

**You say:** "Let's go with the safe migration plan"

```
Perfect! Let me log this change and create a plan.

[Uses log_change(
    file_path="src/models/user.py",
    change_type="refactor",
    description="Rename User.email to User.email_address with safe migration",
    rationale="Consistency with other model fields (phone_number, home_address)",
    affected_components=[
        "user model", "auth system", "email service",
        "API endpoints", "tests", "newsletter system"
    ],
    risk_assessment={
        "data_loss_risk": "low with proper migration",
        "breaking_change": True,
        "performance_impact": "minimal",
        "requires_downtime": False
    },
    rollback_plan="Keep old column for 2 weeks, can rollback migration"
)]

Change logged as #1.

Safe migration plan:
Phase 1: Add new field + alias (Week 1)
  - Add email_address column to database
  - Copy data: email → email_address
  - Add property alias in model
  - Deploy to production

Phase 2: Update code (Week 2)
  - Update all 8 files to use email_address
  - Keep alias for backward compatibility
  - Deploy to production

Phase 3: Remove old field (Week 4)
  - Remove alias
  - Drop email column
  - Final migration

This approach has:
  - Zero downtime
  - Instant rollback capability
  - Backward compatibility during migration
  - Low risk of breaking changes

Shall I help implement Phase 1?
```

**Result:** You avoided breaking production with a field rename!

---

## Scenario 3: "The Authentication System is Too Slow"

### The Situation
Users complain that login is taking 5-10 seconds.

### How DevilMCP Helps Debug and Fix

**You say:** "Login is super slow, need to optimize authentication"

**Claude responds:**

```
Let me help investigate and fix this systematically.

[Uses start_thought_session(
    session_id="perf-auth-slow-2025-11-04",
    context={
        "issue": "Slow authentication (5-10 seconds)",
        "priority": "high",
        "user_impact": "All users affected"
    }
)]

Session started. Let me analyze the authentication system.

[Uses track_file_dependencies(
    file_path="src/auth/authentication.py"
)]

[Uses log_thought_process(
    thought="Authentication takes 5-10 seconds. Need to identify bottleneck.",
    category="analysis",
    reasoning="Performance issue affects all users. Could be: database queries,
              password hashing, session creation, or external API calls.",
    session_id="perf-auth-slow-2025-11-04"
)]

Let me check the authentication code... [reads file]

[Uses log_thought_process(
    thought="Found it! Password hashing using bcrypt with rounds=15.
            This is extremely high (typical is 10-12).",
    category="analysis",
    reasoning="bcrypt rounds=15 takes ~5-10 seconds per hash. This explains
              the slowness. Someone likely set it too high for 'security'.",
    confidence=0.95
)]

[Uses log_thought_process(
    thought="Should reduce bcrypt rounds from 15 to 12",
    category="hypothesis",
    reasoning="Rounds=12 provides excellent security (2^12 iterations) while
              completing in ~200ms. Still very secure but 25x faster."
)]

[Uses log_thought_process(
    thought="Need to handle existing passwords hashed with rounds=15",
    category="concern",
    reasoning="Existing user passwords were hashed with rounds=15. Changing
              the setting won't affect them until they change password. Need
              migration strategy.",
    confidence=0.9
)]

Found the issue! Let me check if changing bcrypt rounds could cause problems:

[Uses analyze_change_impact(
    file_path="src/auth/authentication.py",
    change_description="Reduce bcrypt rounds from 15 to 12"
)]

Impact: LOW
Affected: Just authentication.py
Risk: Existing passwords still work (bcrypt auto-detects rounds)

[Uses log_decision(
    decision="Reduce bcrypt rounds from 15 to 12",
    rationale="Current rounds=15 causes 5-10 second login times. Rounds=12
              provides strong security (recommended by bcrypt docs) while
              being 25x faster (~200ms). bcrypt stores rounds in hash so
              existing passwords unaffected.",
    context={
        "current_rounds": 15,
        "new_rounds": 12,
        "current_time": "5-10 seconds",
        "expected_time": "~200ms",
        "security_impact": "Still very secure"
    },
    alternatives_considered=[
        "Keep rounds=15 - Too slow",
        "Reduce to 10 - Less secure",
        "Switch to Argon2 - Unnecessary complexity for this fix"
    ],
    expected_impact="Login time reduced from 5-10s to ~200ms",
    risk_level="low",
    tags=["performance", "authentication", "security"]
)]

[Uses analyze_reasoning_gaps()]

Gap found: Haven't considered monitoring!

[Uses log_thought_process(
    thought="Should add monitoring for login times",
    category="validation",
    reasoning="Need to verify the fix works and catch if it regresses. Add
              metric to track average login time.",
    confidence=0.9
)]

Perfect! Here's my analysis:

Problem: bcrypt rounds=15 (takes 5-10 seconds)
Solution: Reduce to rounds=12 (takes ~200ms)
Security: Still very secure (2^12 = 4096 iterations)
Risk: Low (existing passwords unaffected)
Improvement: ~25x faster

Would you like me to make this change?
```

**You say:** "Yes, please make the change"

```
[Uses log_change(
    file_path="src/auth/authentication.py",
    change_type="modify",
    description="Reduce bcrypt rounds from 15 to 12",
    rationale="Performance optimization while maintaining security",
    affected_components=["authentication"],
    risk_assessment={"breaking_change": False, "security_impact": "none"},
    rollback_plan="Change constant back to 15"
)]

[Makes the change]

[Uses update_change_status(
    change_id=1,
    status="implemented",
    actual_impact="Login time reduced to ~200ms. No security issues."
)]

[Uses record_insight(
    insight="bcrypt rounds should typically be 10-12. Higher values cause
            significant performance impact with diminishing security returns.",
    source="Authentication performance optimization",
    applicability="Any system using bcrypt password hashing"
)]

[Uses end_thought_session(
    session_id="perf-auth-slow-2025-11-04",
    summary="Fixed slow authentication by reducing bcrypt rounds 15→12",
    outcomes=[
        "Login time: 5-10s → ~200ms",
        "Security maintained",
        "Added login time monitoring",
        "Zero breaking changes"
    ]
)]

✅ Done! Authentication is now ~25x faster.

Changes made:
- Reduced bcrypt rounds: 15 → 12
- Added login time monitoring
- All existing passwords still work

Recommendation: Deploy to production and monitor login metrics.
```

**Result:** You fixed a performance issue with full context, reasoning, and no security compromise!

---

## Scenario 4: "I Want to Refactor the API Layer"

### The Situation
Your API layer is messy with mixed concerns. You want to refactor it.

### How DevilMCP Prevents Refactoring Disasters

**You say:** "I want to refactor the API layer. It's a mess."

**Claude responds:**

```
Major refactoring requires careful planning. Let me analyze the situation.

[Uses analyze_project_structure()]
[Uses build_dependency_graph()]

Your API layer:
- 15 endpoint files
- 45 total routes
- Imported by: frontend, mobile app, admin dashboard
- Imports: database, auth, services, utils

⚠️  This is a high-risk refactoring. Let me check cascade potential:

[Uses analyze_cascade_risk(
    target="src/api/",
    change_type="refactor"
)]

🚨 CASCADE RISK: VERY HIGH (85%)

Cascade chain:
  API routes → Frontend (47 components)
  API routes → Mobile app (23 screens)
  API routes → Admin dashboard (12 pages)
  API routes → Automated tests (67 test files)

If API breaks, 3 applications and all tests break.

[Uses suggest_safe_changes(
    target="src/api/",
    proposed_change="Refactor API layer to separate concerns"
)]

SAFE REFACTORING STRATEGY:

Recommended approach: Parallel implementation
1. Keep old API routes working
2. Build new refactored structure alongside
3. Add feature flag to switch between old/new
4. Migrate consumers gradually
5. Remove old code only when all consumers migrated

DO NOT:
❌ Rename/move endpoints directly (breaks all consumers)
❌ Change response formats (breaks parsing)
❌ Delete old code before migration complete

[Uses log_decision(
    decision="Refactor API with parallel implementation strategy",
    rationale="Gradual migration allows testing and rollback. Zero downtime.
              Can validate new structure before committing.",
    alternatives_considered=[
        "Direct refactor - HIGH RISK: breaks all consumers",
        "Big bang migration - RISKY: no rollback path",
        "Leave it as is - Technical debt keeps growing"
    ],
    risk_level="medium",  # Was high, but parallel strategy reduces risk
    tags=["refactoring", "API", "architecture"]
)]

Would you like me to:
A) Create a detailed parallel migration plan (RECOMMENDED)
B) Proceed with direct refactoring (RISKY - not recommended)
C) Do smaller incremental refactorings instead

I strongly recommend option A or C.
```

**You say:** "Let's do the parallel migration"

```
Excellent choice! Here's the safe migration plan:

[Multiple log_change() calls for each phase]

PHASE 1: Create new structure (Week 1)
  ✓ Create src/api/v2/ directory
  ✓ Implement new organized routes
  ✓ Add feature flag: USE_API_V2
  ✓ Route requests based on flag
  ✓ All tests pass for both versions

PHASE 2: Migrate internal consumers (Week 2-3)
  ✓ Update automated tests
  ✓ Update admin dashboard
  ✓ Monitor for errors

PHASE 3: Migrate frontend (Week 4)
  ✓ Enable flag for 10% of users
  ✓ Monitor error rates
  ✓ Gradually increase to 100%

PHASE 4: Migrate mobile (Week 5)
  ✓ Release app update with v2 support
  ✓ Wait for user update adoption (>80%)
  ✓ Switch flag

PHASE 5: Cleanup (Week 6)
  ✓ Remove old API code
  ✓ Remove feature flag
  ✓ Update documentation

This approach provides:
  ✅ Zero downtime
  ✅ Instant rollback at any phase
  ✅ Gradual validation
  ✅ Monitoring at each step
  ✅ Easy debugging (can compare old vs new)

Shall we start with Phase 1?
```

**Result:** You're refactoring safely with a clear plan and rollback capability!

---

## Scenario 5: "Why Did We Make That Decision 6 Months Ago?"

### The Situation
You're wondering why the team chose PostgreSQL over MongoDB last year.

### How DevilMCP Provides Institutional Memory

**You ask:** "Why did we choose PostgreSQL over MongoDB?"

**Claude responds:**

```
Let me check the decision history.

[Uses query_decisions(
    query="PostgreSQL MongoDB database",
    limit=10
)]

Found decision #3 from 2024-05-10:

DECISION: Use PostgreSQL for main database
MADE BY: Previous team member
DATE: May 10, 2024

RATIONALE:
  "Need strong ACID guarantees for financial transactions. Complex queries
   require JOINs between users, accounts, and transactions. Team has
   PostgreSQL experience. MongoDB's eventual consistency unsuitable for
   money handling."

ALTERNATIVES CONSIDERED:
  1. MongoDB
     - Pro: Great performance, flexible schema
     - Con: Eventual consistency risky for finance
     - Con: Harder to do complex relational queries

  2. MySQL
     - Pro: Widely supported
     - Con: Less advanced features than PostgreSQL

  3. DynamoDB
     - Pro: Fully managed, scales automatically
     - Con: Expensive, vendor lock-in

CONTEXT:
  - Project: FinanceApp
  - Expected users: 10,000-100,000
  - Compliance: PCI-DSS required
  - Budget: Moderate

RISK LEVEL: Medium

EXPECTED IMPACT:
  "Better data consistency, complex queries possible, team productivity"

[Uses analyze_decision_impact(decision_id=3)]

ACTUAL OUTCOME (recorded 2024-08-15):
  "PostgreSQL working excellently. Zero data consistency issues. Complex
   financial reports work perfectly with JOINs. Team happy with choice.
   Only issue was initial migration took longer than expected."

LESSONS LEARNED:
  "PostgreSQL was the right choice for financial data. Plan more time for
   schema design and migrations. JSON column types in PostgreSQL give us
   flexibility where needed."

SUCCESS: ✅ YES
Impact variance: POSITIVE (exceeded expectations)

Summary: You chose PostgreSQL because you're handling money and needed
ACID guarantees, complex relational queries, and data consistency.
MongoDB's eventual consistency was too risky for financial transactions.
The decision proved correct - zero data consistency issues in production.

Would you like more details on any aspect?
```

**Result:** Complete context about past decisions, including rationale and outcomes!

---

## Scenario 6: "Everything is Breaking After My Change"

### The Situation
You changed one function and now 5 tests are failing.

### How DevilMCP Helps Post-Mortem

**You say:** "I changed the payment validation function and now everything's broken!"

**Claude responds:**

```
Let me help investigate and document this for learning.

[Uses track_file_dependencies(
    file_path="src/payments/validation.py"
)]

validation.py is imported by:
- payment_handler.py
- checkout_process.py
- subscription_manager.py
- refund_handler.py
- admin_payment_tools.py

[Uses log_cascade_event(
    trigger="Changed signature of validate_payment() function",
    affected_components=[
        "payment_handler",
        "checkout_process",
        "subscription_manager",
        "refund_handler",
        "admin_tools"
    ],
    severity="high",
    description="Added required parameter to validate_payment(). All 5 callers
                broke because they weren't passing the new parameter. 5 test
                suites failed immediately.",
    resolution="Added default value to new parameter, making it optional. All
               callers work again. Will update callers gradually."
)]

Cascade event logged as #1.

This is a textbook cascade failure:
  - Core function changed (validate_payment)
  - 5 dependent components broke simultaneously
  - Tests caught it before production ✅

Good news: Tests caught it!
Lesson: Breaking changes to widely-used functions cause cascades.

How to prevent next time:
1. Use analyze_cascade_risk() before changing core functions
2. Add parameters as optional (default values)
3. Deprecation period before making required
4. Check who imports the file first

[Uses record_insight(
    insight="When changing function signatures in core modules, always add
            parameters as optional with defaults. Required parameters break
            all callers simultaneously.",
    source="validate_payment cascade failure",
    applicability="Any function used by multiple modules"
)]

Would you like me to help fix the remaining issues?
```

**Result:** You learned from the cascade failure and it's documented for future reference!

---

## Key Takeaways

1. **DevilMCP makes you think before acting** - No more YOLO changes
2. **Provides institutional memory** - Understand why decisions were made
3. **Prevents cascade failures** - Catches high-risk changes early
4. **Tracks your reasoning** - Helps find blind spots
5. **Learns from incidents** - Builds knowledge over time

---

## Try It Yourself!

These scenarios work automatically when you use Claude Code. Just:

1. Open your project in Claude Code
2. Ask questions like the examples above
3. Claude will use DevilMCP tools automatically
4. Get better outcomes with full context

**The AI knows when to use these tools. You just work normally!**
