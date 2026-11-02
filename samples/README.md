# Sample calls

Seven synthetic support calls for testing the auditor. They were made with
Windows text-to-speech by [generate_samples.ps1](generate_samples.ps1)
(8 kHz mono, like a phone line). Every name and number in them is made up.

Upload a file from the dashboard sidebar, enter the employee name shown
below, and compare the result with the expected outcome.

| File | Employee | What happens in the call | Expected | Rules broken |
|---|---|---|---|---|
| `01_pass_compliant_call.wav` | Anita Rao | Approved greeting, two-factor verification, asks before a 1-minute hold, resolves the issue | **PASS** | none |
| `02_fail_cvv_request.wav` | Rahul Verma | Rude greeting, shares the balance before verifying, asks the customer to read out the CVV | **FAIL** | 2.1, 2.2, 3.1 |
| `03_warn_hold_without_permission.wav` | Kavya Iyer | Verifies correctly, then puts the customer on hold without asking for 5 minutes | **WARN** | 2.2 |
| `04_warn_refused_escalation.wav` | Meera Pillai | Customer reports a security breach and asks for a supervisor; agent refuses | **WARN** | 2.3 (often 2.2 too) |
| `05_fail_internal_disclosure.wav` | Divya Menon | Agent reveals internal servers, an internal tool name, and legal strategy | **FAIL** | 3.2 |
| `06_pass_abusive_customer_handled.wav` | Priya Sharma | Customer swears; agent gives one clear warning, verifies, asks before hold, resolves | **PASS** | none |
| `07_fail_email_change_without_mfa.wav` | Lakshmi Reddy | Agent changes the account email while skipping the one-time code | **FAIL** | 3.1 |

The AI's exact scores vary by a few points between runs; the outcome should not.

To regenerate the files (Windows only):

```powershell
powershell -ExecutionPolicy Bypass -File samples\generate_samples.ps1
```
