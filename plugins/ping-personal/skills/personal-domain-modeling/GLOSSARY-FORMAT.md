# GLOSSARY.md Format

## Structure

```md
# {Context Name}

{One or two sentences: what this context is and why it exists.}

## Language

**Order**:
{One or two sentences describing the term.}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Be opinionated.** When several words exist for one concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences at most. Define what it IS, not what it does.
- **Only terms specific to this project.** General programming ideas (timeouts, error types, helper patterns) do not belong, even when the project uses them a lot.
- **Group terms under subheadings** when natural clusters appear. A flat list is fine when they all belong together.

## One area or several

**Single area (most projects):** one `docs/glossary/GLOSSARY.md`.

**Several areas:** `docs/glossary/GLOSSARY-MAP.md` lists each area's glossary file and how the areas relate:

```md
# Glossary Map

## Contexts

- [Ordering](./ordering.md): receives and tracks customer orders
- [Billing](./billing.md): generates invoices and processes payments

## Relationships

- **Ordering -> Billing**: Ordering emits an OrderPlaced event; Billing consumes it to create an invoice
```

How to tell which structure applies:

- If `docs/glossary/GLOSSARY-MAP.md` exists, read it to find the areas.
- If only `docs/glossary/GLOSSARY.md` exists, there is one area.
- If neither exists, create `docs/glossary/GLOSSARY.md` when the first term is resolved.
