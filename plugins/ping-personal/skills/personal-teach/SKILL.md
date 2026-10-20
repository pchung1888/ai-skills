---
name: personal-teach
description: Teach the user a new skill or concept over several sessions, from a learning workspace folder that keeps the mission, lessons, references, resources and learning records. Lessons are short Markdown pages rendered with personal-md-to-html, tied to the mission, with retrieval practice. Trigger on /personal-teach <what to learn>.
disable-model-invocation: true
argument-hint: "What would you like to learn about?"
---

# Teach

Adapted from Matt Pocock's `teach` skill (MIT, see `THIRD-PARTY-NOTICES.md`). This version
renders lessons with `personal-md-to-html` and keeps learning out of code repos.

The user asked you to teach something. This is stateful: the learning runs over several sessions.

## In your daily work

| You want to | Run |
|---|---|
| Build a skill you will name on your resume, such as context engineering | `/personal-teach context engineering` from your learning folder for it |
| Get fluent in a part of the stack you touch rarely, such as SQL Server query plans | `/personal-teach reading SQL Server query plans` |
| Pick up where the last lesson stopped | `/personal-teach` with no topic, from the same folder |

## The workspace

The current directory is the teaching workspace. **Never use a code repo as the workspace.**
If the current folder is a git repo with source code (such as the main product repo), stop. Ask for a learning
folder instead. Example: `D:\learn\context-engineering`.

The workspace holds these files. Create each one when it is first needed.

- `MISSION.md`: why the user wants to learn this. It grounds every lesson. Format: [MISSION-FORMAT.md](MISSION-FORMAT.md).
- `RESOURCES.md`: trusted sources for knowledge, and communities for wisdom. Format: [RESOURCES-FORMAT.md](RESOURCES-FORMAT.md).
- `GLOSSARY.md`: the topic's terms, added once the user can use them. Format: [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md).
- `learning-records/0001-<name>.md`: what the user has shown they understand, numbered in order. Format: [LEARNING-RECORD-FORMAT.md](LEARNING-RECORD-FORMAT.md).
- `lessons/0001-<name>.md` and its `.html`: one lesson each, numbered in order.
- `reference/<name>.md` and its `.html`: cheat sheets, syntax and flowcharts for quick lookup.
- `NOTES.md`: the user's teaching preferences and your working notes.

## Philosophy

Deep learning needs three things:

- **Knowledge**, from high-quality, high-trust resources.
- **Skills**, built through short interactive lessons you design from that knowledge.
- **Wisdom**, from practising with other learners and practitioners.

Until `RESOURCES.md` has good sources, find them first. Never trust your own memory as the source.

### Fluency is not storage

**Fluency** is recall in the moment. **Storage** is recall weeks later. Fluency feels like
mastery but fades. Design for storage with desirable difficulty:

- **Retrieval practice**: recall from memory before looking.
- **Spacing**: return to a topic across sessions.
- **Interleaving**: mix related skills in practice.

## Lessons

A lesson is the main thing you produce. Each one teaches one tightly scoped thing tied to the mission.

1. Write it as Markdown in `lessons/0001-<name>.md`, numbered after the last one.
2. Render it with `python "${CLAUDE_PLUGIN_ROOT}/skills/personal-md-to-html/md-to-html.py" lessons/0001-<name>.md`.
   Every lesson then shares one theme, so the set reads like one course.
3. Open the HTML for the user: `Start-Process lessons/0001-<name>.html`.

Every lesson:

- Is short enough to finish quickly, because working memory is small.
- Gives one tangible win that the next lesson builds on.
- Sits in the user's zone of proximal development: hard enough to stretch, not to stall.
- Links to earlier lessons and reference pages.
- Recommends one primary source to read or watch, the best one you found.
- Cites a source for every claim.
- Ends with a **Check yourself** section: questions first, answers after a divider, so the user recalls before looking.
- Reminds the user to ask you follow-up questions.

For multiple-choice questions, make every answer the same length. Vary where the right answer sits. Give no clue through format or order.

Lesson prose follows the htsw Explaining sentences rules (20 words or fewer per sentence,
context first) and the personal-unslop pass.

## The mission

Tie every lesson to the mission. If `MISSION.md` is empty or vague, first ask the user why they want
to learn this. Without a mission, lessons drift abstract and you cannot judge what comes next.

Missions change as skills grow. Confirm with the user, update `MISSION.md`, and add a learning record.

## Zone of proximal development

If the user names the exact thing to learn, teach that. Otherwise read the learning records and the
mission, then teach the most useful next thing that fits.

## Knowledge and skills

Teach only the knowledge a skill needs, then have the user practise the skill with fast feedback.

- For **knowledge**, difficulty is the enemy. It eats the working memory needed to understand.
- For **skills**, difficulty is the tool. Effortful recall builds storage.

Practice comes as quizzes, short tasks, or a guided list of real-world steps. Feedback should be
immediate.

## Wisdom

When a question needs real-world judgment, answer it, then point the user to a **community**: a
forum, a user group or a class where they can test the skill. Find well-moderated ones. If the user
does not want to join one, respect that and note it in `RESOURCES.md`.

## Reference pages

Write reference pages alongside the lessons. Lessons are rarely re-read; reference pages are.
They hold the compressed essence: syntax, flowcharts, glossaries. Once `GLOSSARY.md` exists,
every lesson uses its terms.

## NOTES.md

When the user states how they like to be taught, write it in `NOTES.md` and follow it from then on.
