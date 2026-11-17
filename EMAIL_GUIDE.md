# Gmail delivery after certificate review

Developed and maintained by **[Willy Wanjau (@morio1)](https://github.com/morio1)**.

## What this module does

After stamping/signing and reviewing the exported PDFs, open **Email reviewed certificates**. Each recipient is mapped to exactly one output PDF per CSV row. The application validates that the attachment is listed as successful in the selected export audit and still has the recorded SHA-256 hash. It does not guess an email address from a student's name or filename.

Loading, validating and previewing a plan do not send anything. Sending begins only when you tick the review checkbox and press **Send reviewed batch via Gmail**. One message goes to one address with one PDF attached. Other students' certificates are not attached to that message and recipients are not combined in To/CC/BCC.

## Google account setup

This version uses Gmail SMTP over verified TLS at `smtp.gmail.com:465`, with your Gmail/Google Workspace address and a Google app password. The password is masked in the interface, used in memory and cleared from the input when sending starts. It is not written to settings, the journal or GitHub. Enter it in the application, not in a chat or CSV.

Google app passwords require 2-Step Verification and account eligibility; Workspace administrators or account security settings may prevent their use. This version does not implement a Sign in with Google/OAuth flow. Do not disable account protections to make it work; ask your administrator about an approved sending method if app passwords are unavailable.

Official guidance: [Google app passwords](https://support.google.com/accounts/answer/185833), [sending email from an application](https://support.google.com/a/answer/176600), and [Workspace sending limits](https://support.google.com/a/answer/166852).

## Step-by-step workflow

1. Finish stamping/signing. Inspect the processed PDFs and reconcile the export audit. If stamping and signing in two passes, use the final pass's output folder and audit for email.
2. Click **Email reviewed certificates**. The most recent output folder and audit are suggested. You can browse to another processed folder and its corresponding `audit-...json` file.
3. Click **Create recipient CSV template**. It includes only successful output paths. Fill in the actual email and recipient name from your authoritative student/recipient list. Keep each certificate path unchanged. Save as UTF-8 CSV from Excel.
4. Browse to that CSV. Enter the sending Google address, subject and message. Supported placeholders are `{name}` and `{certificate}`. The latter expands to the attachment's filename.
5. Click **Load & validate plan**. A missing PDF, changed PDF, invalid address, duplicate recipient/path pair, or unsuccessful/non-audited output blocks plan loading. PDF attachments are limited to 18 MiB each to allow room for email encoding overhead.
6. Select each row to preview the exact To address, subject, message and attachment path. Use **Preview attached PDF** to inspect the actual file and navigate its pages. You are responsible for confirming that each address belongs to the named certificate recipient.
7. Enter the Google app password and choose **Max messages this run**. The default is 100; the application permits 1-1,000. This is not a guarantee that Google permits that many messages for your account.
8. Tick **I reviewed recipients, attachments and message content**, then press **Send reviewed batch via Gmail**. The application sends sequentially with a pause between messages. **Stop** stops before the next message; a message already in progress may still be accepted.
9. Inspect the result and local `email-delivery.jsonl` journal in the processed output folder. Gmail acceptance is not proof of inbox delivery. Review Gmail Sent, bounce messages and recipient reports as needed.

Example mapping:

```csv
email,certificate,recipient_name
student1@example.test,Nairobi/Student-A.pdf,Student A
student2@example.test,Mombasa/Student-B.pdf,Student B
```

These are fictitious example addresses. Replace them with reviewed real recipient addresses before sending. Paths are relative to the selected processed PDF folder. Only mapped rows are considered for delivery; an unmapped certificate is not emailed.

## A batch of 1,000

Stamping/signing 1,000 PDFs and emailing 1,000 recipients are separate operations. Google imposes account-specific daily, recipient and abuse limits. It may reject or temporarily restrict sending, and the application does not bypass these limits. Use an administrator-approved Workspace setup and batches within your remaining quota. Splitting a batch does not reset a daily quota.

Keep the same output folder and journal between delivery sessions. The sender address, recipient address and attachment hash form the duplicate-protection key. Previously accepted, in-progress or uncertain attempts are not automatically sent again, even if the subject changes. For another session, load the same reviewed mapping and continue within your permitted allowance.

## Journal and failure handling

| Status | Meaning / next step |
| --- | --- |
| `attempting` | Written and flushed before sending. After a crash, treat this as uncertain and check Gmail Sent before any manual recovery |
| `accepted` | Gmail accepted the message for onward delivery; it may still bounce or go to spam |
| `rejected` | The recipient was explicitly refused; correct the address/cause before another attempt |
| `uncertain` | A connection/send error made delivery status uncertain. Sending stops; the app does not automatically retry that attachment/recipient |
| `not_attempted` | A run limit, cancellation or earlier interruption left the row unsent in that run's result |
| `skipped_previous_or_uncertain` | The journal blocks a possible duplicate; check prior records/Gmail Sent |

A `.email-send.lock` prevents simultaneous delivery from the same folder. If the process crashes, the lock may remain. Before removing a stale lock, confirm no sending process is running and inspect the journal and Gmail Sent. Never delete the journal just to force a resend: you can create duplicate deliveries.

Journals and recipient CSVs contain personal information. Keep them local and access-controlled; they are excluded from repository packaging. Back them up securely if you need delivery continuity. Moving PDFs without their journal removes that folder's duplicate history.

## Verification limits

Tests use a fake SMTP service: no real credentials or recipient emails were used during development. Tests verify one-recipient/one-attachment messages, attachment hashes, review gating, duplicate protection, run limits and uncertain-send handling. A real Gmail sign-in/send still needs to be tested by the operator using an approved account and a controlled recipient before a production batch. Bounce tracking, OAuth, inbox-delivery confirmation and provider-wide quota discovery are not implemented.
