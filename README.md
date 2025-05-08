I'd like to create a small app that uses an LLM to automatically archive emails in my inbox that I don't need.

We have an app `training_data.py` that I used to classify a bunch of emails for reference, saved to `classifeid_email.json`

```
  {
    "subject": "CORVIDAE STATUS CHECK ERROR",
    "sender": "zdicklin@gmail.com",
    "body_snippet": "Error checking Corvidae status: Exception: Request failed for http://140.82.8.182:8080 returned code",
    "reason": "This is a status update from a broken cryptobot service. Archive it.",
    "action": "archive"
  },
  {
    "subject": "Jahna and other neighbors are planning to attend Beginners to Experienced,...",
    "sender": "Weekend Events in Cherrywood Park <no-reply@rs.email.nextdoor.com>",
    "body_snippet": "See 7 local events happening this weekend                             ",
    "reason": "Nextdoor spam, never reading this",
    "action": "archive"
  },
  {
    "subject": "You have a new explanation of benefits",
    "sender": "Anthem Blue Cross Communications <DoNotReply-MemberComm@email.anthem.com>",
    "body_snippet": "Log in to review your claims details. View email in a browser Anthem Blue Cross Log in to see your e",
    "reason": "Infomation from my healthcare provider on a recent visit. Worth reviewing, keep it",
    "action": "inbox"
  },
```

For this app, I'd like you to:

- Loads `inbox_saved.txt`, a list of message IDs we already scanned and decided to keep in the Inbox
- Fetch my entire inbox (page by page)
- Check each email in my inbox
- Call Gemini with a prompt to classify each email (that isn't in inbox_saved.txt). It should include a preamble instructions, the list of `classified_emails.json` for reference/examples, and ask for a decision [ARCHIVE] or [INBOX].
- If [ARCHIVE], archive the email and move on
- If [INBOX], do not act on the email. Save the message ID to `inbox_saved.txt` to ignore the email again on subsequent classification runs
- Run until the entire inbox has been processed
- Include lots of debugging output

Gemini API key is in .env as GEMINI_API_KEY