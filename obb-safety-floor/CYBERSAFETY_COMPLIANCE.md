# Cybersafety & Child Privacy Compliance Specification (`CYBERSAFETY_COMPLIANCE.md`)

**Module:** `obb-safety-floor` (One Big Backend — Module 7: K–8 Threat-Recognition & Social Safety Floor)
**Jurisdiction:** Manitoba, Canada (Public School Divisions & Manitoba Catholic Schools)
**License:** GNU AGPLv3 | **Attestation:** `probabilistic_structural` ($\Box$ Verified)

---

## 1. Executive Summary: "Zero-PII By Design"

Most educational technology fails school-board procurement and parental trust because it collects student personal information, requires student accounts, or exposes children to unverified generative AI and third-party tracking pixels.

**`obb-safety-floor` eliminates these regulatory liabilities at the architectural root:**

1. **Zero Student Accounts or Personal Identifiable Information (PII)**:
   - Students **never** log in, enter names, email addresses, birthdates, student IDs, or free-text personal disclosures.
   - Database tables (`safety_boards`, `safety_modules`, `safety_commits`) store **only** the curriculum modules, dinner-table parent scripts, and cryptographic Git revision logs.
2. **Manitoba FIPPA & PHIA Compliance**:
   - Under Manitoba's *Freedom of Information and Protection of Privacy Act* (FIPPA), a public body (school division) must protect "personal information" (`s. 1(1)`). Because `obb-safety-floor` processes **zero bytes of student personal information**, it cannot leak student records.
3. **Federal PIPEDA & Children's Privacy (COPPA-Equivalent) Compliance**:
   - Every HTTP response enforces strict privacy headers:
     - `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'`
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: DENY`
     - `Referrer-Policy: no-referrer`
     - `Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()`
   - Zero third-party scripts, zero ad trackers, zero external fonts, and zero behavioral telemetry.
4. **Archdiocesan "Safe Environment" & Parental Subsidiarity Compliance**:
   - **No Adult-to-Minor Direct Messaging**: The software contains no chat rooms, direct messaging, or 1-on-1 communication channels.
   - **100% Parental & Pastoral Pre-Inspection**: Parents and pastors can view every word of every K–8 module and its corresponding **Family Dinner-Table Practice Script** without an account.
   - **Cryptographic Anti-Tampering (`safety_commits`)**: Every lesson has a SHA-256 content hash. If any unauthorized edit or ideological drift is introduced, the system flags the diff and allows **1-Click Undo** back to the Board/Pastor-Approved baseline commit.
5. **Deterministic Content Filter (Anti-Ideological / Age-Appropriate Guardrail)**:
   - All curriculum edits pass through a deterministic content validator (`validate_child_safety_content`) that blocks external URLs, HTML script injection, personal data collection prompts, or off-topic adult/sexualized terminology—keeping the floor strictly focused on **behavioural threat recognition** (*Secrets vs. Surprises*, *Manipulation Spotting*, *Online Coercion*, and *No-Go-Tell*).
