You're in `D:\QAScrub` and the production IPs are saved. Two quick checks before Step 1:
- **Hash.** You didn't paste it yet. If you skipped the check, run it now: ...
- **API server.** Does this client have a separate one? A yes or no is enough.

## Step 1a: stop everything that can send mail (QA web server)

This step changes the box: it stops the app services, scheduled tasks and web site.
It asks before it changes anything.

1. Right-click PowerShell and choose **Run as administrator**.
2. Run these four lines: ...
3. A **CONFIRM THIS IS THE QA BOX** screen appears. **Don't type YES yet.** Read me these
   three things from it:
   - the machine name it shows,
   - the "Production servers" IP list (does it match what you typed?),
   - every service name in the list.

## Why I stop you at the confirm screen

STOPALL is the first step that changes the box. Its confirm screen is the last point where
nothing has happened yet. ...

## TL;DR
...
