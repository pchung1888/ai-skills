# Reading order

Teach files in build order: each file uses only names that an earlier file introduced. Then the user
never meets a name they have not seen. Adapt the order to the real folder. Skip a row whose file does
not exist, and add a row for a file that has no match here.

## React + Vite web app

| Order | File (typical) | Why it comes here | In ASP terms |
|---|---|---|---|
| 1 | `package.json` | Names every library and the build commands. | The list of COM DLLs a site needs. |
| 2 | `vite.config.ts` | Says how the build runs, the base path and the dev proxy. | IIS site settings plus the vdir path. |
| 3 | `index.html`, `config.ts` | The one HTML shell, and the per-box settings. | `global.asa` settings and one ASP shell page. |
| 4 | `main.tsx` | Starts React and mounts the app into the shell. | `Application_OnStart`. |
| 5 | `routes.tsx` | Maps each URL to a page. | The list of `.asp` files a URL can reach. |
| 6 | `router.tsx` (or the router library setup) | Reads the URL and picks the page. | IIS picking the `.asp` file. |
| 7 | API helper (`api.ts`) | One function for every call to the service: cookie, headers, errors. | The include file that wraps `AppDAL.dll` calls. |
| 8 | Small shared parts (keep-alive, popups, calendar) | The pages below use them. | Shared include files. |
| 9 | Browse page | Filter, grid, sort, paging. | `XxxBrowse.asp`. |
| 10 | Detail page | Load, save, delete, conflicts. | `XxxDetail.asp` plus its save post-back. |

## .NET 10 service (ASP.NET Core, Kestrel)

| Order | File (typical) | Why it comes here | In ASP terms |
|---|---|---|---|
| 1 | `*.csproj` | The target framework and the packages. | The VB6 project file and its references. |
| 2 | `Program.cs` top | Port, certificate, path base, services, middleware. | IIS bindings plus `global.asa`. |
| 3 | Settings classes, `appsettings*.json` | Connection string and per-box values. | `Application` variables set at start. |
| 4 | Access check (session, permission gate) | Who may call what. | The session and permission check at the top of every page. |
| 5 | Data layer (`I*Data.cs`, `*Data.cs`, SQL helper) | Stored procedure calls. | `AppDAL.dll` and `Do While Not rs.EOF`. |
| 6 | `Program.cs` endpoints | One URL per action, calling the data layer. | One `.asp` page or post-back per action. |
| 7 | Side calls (cache clear, mail) | Calls to old code or other systems. | An `XMLHTTP` call to another ASP page. |

## Install and run

| Order | File (typical) | Why it comes here | In ASP terms |
|---|---|---|---|
| 1 | Install script | Builds, publishes, registers the service or task. | The deploy checklist for a DLL and a vdir. |
| 2 | Start script and scheduled task | Keeps the service running after a reboot. | The IIS app pool start mode. |
| 3 | IIS entry page or redirect | Sends users from the old page to the new one. | A redirect at the top of an `.asp` page. |

## Split rule

A file of more than 60 lines, or with more than one job, becomes sub-steps. Split at the section
borders the code already has: types and helpers, state and load, event handlers, derived values,
the returned screen (JSX). Show the sub-step table before the first sub-step.
