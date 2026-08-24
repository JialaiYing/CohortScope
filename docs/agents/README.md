# Agent roster

Specialists run in **separate chats**. Start each with the matching role file in this folder (copy the text below the horizontal rule).

The **Project Manager** is the default/overall chat (`docs/agents/project-manager.md`) — status, routing, phase gates.

| Agent | Role doc | Launch prompt | `tasks.md` role key |
|---|---|---|---|
| Project Manager | [project-manager.md](project-manager.md) | (main chat) | `any` / coordination |
| Data Engineer | [data-engineer.md](data-engineer.md) | [../launch/data-engineer.md](../launch/data-engineer.md) | `data` |
| Computer Vision | [computer-vision.md](computer-vision.md) | [../launch/computer-vision.md](../launch/computer-vision.md) | `cv` |
| Feature Engineering | [feature-engineering.md](feature-engineering.md) | [../launch/feature-engineering.md](../launch/feature-engineering.md) | `features` |
| Statistics | [statistics.md](statistics.md) | [../launch/statistics.md](../launch/statistics.md) | `stats` |
| Literature | [literature.md](literature.md) | [../launch/literature.md](../launch/literature.md) | `literature` |
| Code Reviewer | [code-reviewer.md](code-reviewer.md) | [../launch/code-reviewer.md](../launch/code-reviewer.md) | `review` |

## How to run in parallel

1. Keep one chat as Project Manager (general help / progress).
2. For each specialist needed now, open a new Agent chat.
3. Paste the contents **below the horizontal rule** from that role’s file in this folder (or `@` it and say “follow this”).
4. Point them at the current phase in `docs/tasks.md`.

Do **not** invent extra generalist engineering agents beyond this roster.
