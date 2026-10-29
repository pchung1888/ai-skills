* Insight: On a live box, the safest deploy is one step at a time. You run a step, paste the output, and I check it before the next one. Nothing changes on the server until step 3.

We start with a read-only survey. It changes nothing. It tells us the real DLL path, the app pool, and the web root before we touch anything.

## The whole plan (so you see the shape)

| Step | What happens | Changes the server? |
|---|---|---|
| 1 | Survey: files, registered DLL path, app pool, web root | No |
| 2 | Back up the old DLL and the current ASP pages | Adds a backup folder only |
| 3 | Stop the app pool (users see an outage from here) | Yes |
| 4 | Unregister old DLL, copy new DLL, register new DLL | Yes |
| 5 | Unzip the ASP pages over the web root | Yes |
| 6 | Start the app pool, smoke test, check the event log | Yes |
| R | Rollback: restore step 2 backups, re-register old DLL | Only if needed |

## Step 1 - read-only survey

Open PowerShell **as Administrator** on the prod box. Paste this block and send me the full output.

```powershell
# 1a. What did you copy in? Sizes and dates of the new files.
Get-ChildItem D:\Deploy\2026-10-27 | Format-Table Name, Length, LastWriteTime

# 1b. Old and new DLL versions side by side.
(Get-Item C:\AppHost\bin\App.dll).VersionInfo | Format-List FileVersion, ProductVersion
Get-ChildItem D:\Deploy\2026-10-27 -Filter *.dll | ForEach-Object { $_.FullName; $_.VersionInfo.FileVersion }

# 1c. Which file path is COM really using for the app? (32-bit registry view)
Get-ChildItem Registry::HKEY_CLASSES_ROOT\WOW6432Node\CLSID -ErrorAction SilentlyContinue |
  ForEach-Object { $p = Join-Path $_.PSPath 'InprocServer32'; if (Test-Path $p) { $v = (Get-ItemProperty $p).'(default)'; if ($v -like '*App.dll*') { "$($_.PSChildName)  $v" } } }

# 1d. App pools, and whether 32-bit is on (a VB6 DLL needs it).
Import-Module WebAdministration
Get-ChildItem IIS:\AppPools | ForEach-Object { "$($_.Name)  state=$($_.State)  32bit=$($_.enable32BitAppOnWin64)" }

# 1e. Sites and their physical folders (this is where the ASP pages go).
Get-Website | Format-Table Name, State, PhysicalPath
```

## What I need back from you

1. The output of all five parts above.
2. Is this a maintenance window, or are traders logged in right now?
3. Do you have release notes saying the new DLL kept **binary compatibility**? Binary compatibility is a VB6 build setting that keeps the same COM class IDs. If it broke, step 4 needs an extra unregister and I will adjust.

## Things I do not know yet

- `UNKNOWN`: the app pool name and web root path. Step 1d and 1e will show them.
- `UNKNOWN`: whether the zip holds only changed pages or the full site. Please list the zip contents too if it is easy.
- `UNKNOWN`: whether other COM DLLs sit beside App.dll in `C:\AppHost\bin`. If so, tell me before step 4.

## Why step 1 is read-only and why the registry check matters

- A COM client like ASP finds the DLL through the registry, not the folder. The `InprocServer32` key holds the real path. If it points somewhere other than `C:\AppHost\bin`, copying there would change nothing. Step 1c proves the path. (`INFERRED`: I assume a 64-bit Windows Server, so the 32-bit view is under `WOW6432Node`.)
- A VB6 DLL is 32-bit. It must be registered with `C:\Windows\SysWOW64\regsvr32.exe`, not the default one. I will spell that out in step 4.
- IIS holds a lock on a loaded DLL. That is why step 3 stops the app pool before the copy.

## TL;DR

- Run the step 1 block in an admin PowerShell; paste all output back.
- Tell me if users are live and whether binary compatibility was kept.
- Do not stop, copy or register anything yet; step 2 is the backup.
