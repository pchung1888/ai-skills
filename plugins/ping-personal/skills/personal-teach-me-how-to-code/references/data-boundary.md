# Data boundary steps

The data boundary is where the new code calls the real backend: a stored procedure, a database
query or an outside API. In a converted app, that backend is often the part that did not change.
So these steps show the user how the new stack talks to the backend they already know.

## Plan: one step per kind of call

Add one dedicated step for each kind of backend call the code makes. Typical kinds:

| Kind | One request to trace |
|---|---|
| Auth or permission | The check that runs before any data call. |
| Read a list | The browse or search call. |
| Read one | The fetch of one record. |
| Write | The save, insert or delete. |

Each step traces one real request end to end: screen or client, URL, endpoint, data class,
backend call, result, HTTP status, screen again. Skip a kind the code does not have, and say so
under the plan table.

## Step: the whole wiring chain in one place

A step about an interface shows the whole wiring chain in one place. First, name every class that
shares the name, in a table:

| Name | Kind | File:line | Job |
|---|---|---|---|
| `IOrderData` | interface | `IOrderData.cs:3` | The contract the endpoints call. |
| `SqlOrderData` | implementation | `SqlOrderData.cs:8` | Calls the stored procedures. |
| `CachedOrderData` | decorator | `CachedOrderData.cs:5` | Wraps the SQL class with a cache. |

Then show, in order, with a real excerpt for each link:

1. The interface.
2. The registration: the DI line (`builder.Services.AddScoped<IX, SqlX>()`) or the factory.
3. The caller: the endpoint or page parameter that receives the interface.
4. The implementation method.
5. The backend call itself: the procedure name, the parameters, how the result is read.

End with an ASCII diagram of the same chain:

```text
Program.cs registration -> endpoint parameter (IX) -> SqlX.Method -> EXEC dbo.usp_X -> result
```

## Mapping table for each backend call

For each backend call, write a mapping table: each parameter, its direction, and how the result is
read, mapped to the old-stack call. For ASP Classic, map to the ADO `Command` object.

| Parameter or result | New code | Old stack (ASP ADO) |
|---|---|---|
| `@Id int` input | `new { Id = id }` | `cmd.Parameters.Append cmd.CreateParameter("@Id", adInteger, adParamInput, , id)` |
| `@Name` output | `p.Add("@Name", dbType: DbType.String, direction: ParameterDirection.Output)` then `p.Get<string>("@Name")` | `adParamOutput`, read after `cmd.Execute` |
| Return code | `ParameterDirection.ReturnValue` | `adParamReturnValue` |
| Recordset | `QueryAsync<T>` returns a list | `Set rs = cmd.Execute` then `Do While Not rs.EOF` |

Then say how each return code or empty result becomes an HTTP status, from the real code. Example
shape (fill from the code, never from this example): `0 -> 200 OK`, `1 -> 409 Conflict`,
`no row -> 404 Not Found`.

A summary table helps before the per-call sections:

| Job | How the backend answers | How the new code reads it |
|---|---|---|
| Browse | Recordset | `QueryAsync` |
| Fetch one | OUTPUT parameters | `ExecuteAsync` plus `p.Get` |
| Save | Return code | `ReturnValue` parameter |

## Excerpts at the boundary

Never cut the key line of an excerpt with `...`. At the boundary the key lines are the registration,
the procedure name, the parameter list and the line that reads the result. Elide only lines that are
not the point of the step, and say what the `...` hides.

## Project parity file

If the project has a parity or mapping file (old page to new endpoint, old call to new call), read
it before the plan. Use its names for pages, endpoints and procedures, and link to it from the
mapping tables. Do not copy its project-specific content into this skill.
