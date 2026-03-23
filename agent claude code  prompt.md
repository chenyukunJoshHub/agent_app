# Multi-Tool AI Agent — Full Implementation

Build a production-grade Multi-Tool AI Agent with the following complete specification.
Implement everything end-to-end in a single pass. Do not skip any module.

---

## Tech Stack

Backend:
- Python 3.11+
- FastAPI (async, SSE streaming)
- LangChain v1.x + LangGraph v1.x
- langgraph-checkpoint-postgres v3.x (psycopg3, NOT asyncpg)
- AsyncPostgresSaver + AsyncPostgresStore
- Tavily search API

Frontend:
- Next.js 15 (App Router)
- React 19
- TypeScript
- Tailwind CSS v4
- shadcn/ui components
- Framer Motion (animations)

Database:
- Supabase (local Docker, PostgreSQL)

Testing:
- Playwright (visual mode, headed)
- pytest + pytest-asyncio (backend)

---

## Project Structure
```
/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   └── postgres.py
│   ├── agent/
│   │   ├── executor.py
│   │   ├── langchain_engine.py
│   │   └── middleware/
│   │       ├── memory.py
│   │       └── trace.py
│   ├── memory/
│   │   ├── manager.py
│   │   └── schemas.py
│   ├── skills/
│   │   ├── registry.py
│   │   ├── manager.py            # SkillManager: scan, build_snapshot, budget
│   │   └── definitions/          # SKILL.md files
│   │       ├── legal-search/SKILL.md
│   │       ├── csv-reporter/SKILL.md
│   │       └── contract-analyzer/SKILL.md
│   ├── tools/
│   │   ├── registry.py
│   │   ├── web_search.py
│   │   ├── csv_analyze.py
│   │   ├── send_email.py         # mock HIL tool
│   │   └── skill_tool.py         # activate_skill @tool
│   ├── prompt/
│   │   ├── builder.py
│   │   └── templates.py
│   ├── context/
│   │   └── token_budget.py       # TokenBudget, slot tracking, compression events
│   ├── observability/
│   │   └── tracer.py
│   └── supabase/
│       └── migrations/
│           └── 0001_init.sql
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   └── InputBar.tsx
│   │   ├── react-trace/
│   │   │   ├── ReActPanel.tsx        # full ReAct chain visualization
│   │   │   ├── ThoughtStep.tsx
│   │   │   ├── ToolCallStep.tsx
│   │   │   └── ObservationStep.tsx
│   │   ├── context-window/
│   │   │   ├── ContextWindowPanel.tsx  # token budget viz (like /context cmd)
│   │   │   ├── SlotBar.tsx
│   │   │   └── CompressionLog.tsx
│   │   ├── skills/
│   │   │   ├── SkillPanel.tsx
│   │   │   ├── SkillCard.tsx
│   │   │   └── SkillDetail.tsx
│   │   ├── hil/
│   │   │   └── HILConfirmDialog.tsx
│   │   └── ui/                        # shadcn/ui components
│   ├── hooks/
│   │   ├── useSSE.ts
│   │   ├── useContextWindow.ts
│   │   └── useSkills.ts
│   ├── lib/
│   │   └── api.ts
│   └── types/
│       └── index.ts
│
├── tests/
│   ├── e2e/
│   │   ├── playwright.config.ts
│   │   ├── chat.spec.ts
│   │   ├── react-trace.spec.ts
│   │   ├── context-window.spec.ts
│   │   ├── skills.spec.ts
│   │   └── hil.spec.ts
│   └── backend/
│       ├── test_skill_manager.py
│       ├── test_memory.py
│       └── test_token_budget.py
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Environment Variables (.env.example)
```env
# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-sonnet-4-6

# Tools
TAVILY_API_KEY=your_key

# Storage
SUPABASE_DB_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Agent
MAX_ITERATIONS=10
MAX_EXECUTION_TIME=60
WORKING_TOKEN_BUDGET=32768
OUTPUT_TOKEN_RESERVE=8192

# Features
ENABLE_LONG_TERM_MEMORY=true
ENABLE_SKILLS=true
ENABLE_HIL=true
ENABLE_TRACE=true
ENABLE_RAG=false
```

---

## Backend Implementation

### 1. config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    tavily_api_key: str = ""
    supabase_db_url: str
    max_iterations: int = 10
    working_token_budget: int = 32768
    output_token_reserve: int = 8192
    enable_long_term_memory: bool = True
    enable_skills: bool = True
    enable_hil: bool = True
    enable_trace: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

### 2. db/postgres.py

Use `langgraph-checkpoint-postgres` v3.x with psycopg3 (NOT asyncpg).
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from psycopg.rows import dict_row
from config import settings

async def create_stores():
    checkpointer = AsyncPostgresSaver.from_conn_string(
        settings.supabase_db_url,
        connection_kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
    )
    await checkpointer.setup()

    store = AsyncPostgresStore.from_conn_string(settings.supabase_db_url)
    await store.setup()

    return checkpointer, store
```

### 3. context/token_budget.py

Implement `TokenBudget` dataclass with all 10 slots tracked in real time.
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SlotUsage:
    slot_id: str           # "①" through "⑩"
    name: str              # "system_prompt", "active_skill", etc.
    max_tokens: int
    used_tokens: int
    ephemeral: bool = False
    enabled: bool = True
    overflow: bool = False

@dataclass
class CompressionEvent:
    turn: int
    reason: str            # "history_overflow", "slot_budget_exceeded"
    tokens_before: int
    tokens_after: int
    tokens_saved: int

@dataclass
class TokenBudgetState:
    working_budget: int = 32768
    output_reserve: int = 8192
    slots: list[SlotUsage] = field(default_factory=list)
    compression_events: list[CompressionEvent] = field(default_factory=list)
    total_turns: int = 0
    active_skill_name: Optional[str] = None

    @property
    def input_budget(self) -> int:
        return self.working_budget - self.output_reserve

    @property
    def total_used(self) -> int:
        return sum(s.used_tokens for s in self.slots if s.enabled)

    @property
    def remaining(self) -> int:
        return self.input_budget - self.total_used

    @property
    def usage_pct(self) -> float:
        return round(self.total_used / self.input_budget * 100, 1)

    def to_dict(self) -> dict:
        return {
            "working_budget": self.working_budget,
            "output_reserve": self.output_reserve,
            "input_budget": self.input_budget,
            "total_used": self.total_used,
            "remaining": self.remaining,
            "usage_pct": self.usage_pct,
            "total_turns": self.total_turns,
            "active_skill_name": self.active_skill_name,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "name": s.name,
                    "max_tokens": s.max_tokens,
                    "used_tokens": s.used_tokens,
                    "ephemeral": s.ephemeral,
                    "enabled": s.enabled,
                    "overflow": s.overflow,
                }
                for s in self.slots
            ],
            "compression_events": [
                {
                    "turn": e.turn,
                    "reason": e.reason,
                    "tokens_before": e.tokens_before,
                    "tokens_after": e.tokens_after,
                    "tokens_saved": e.tokens_saved,
                }
                for e in self.compression_events
            ],
        }
```

Implement `count_tokens_approx(text: str) -> int` using character-based estimation:
- Chinese chars: `count / 1.5`
- Other chars: `count / 4`

### 4. skills/manager.py — SkillManager (Critical Module)

Implement the full SkillManager based on the Agent Skill Architecture v3:
```python
import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

SKILLS_DIR = Path(__file__).parent / "definitions"
MAX_SKILL_FILE_BYTES = 256_000
MAX_SKILLS_IN_PROMPT = 150
MAX_SKILLS_PROMPT_CHARS = 30_000

@dataclass
class SkillDefinition:
    id: str
    name: str
    version: str
    description: str        # trigger decision, max 1024 chars
    file_path: str
    tools: list[str]
    mutex_group: Optional[str]
    priority: int
    status: str             # active | disabled | draft
    disable_model_invocation: bool
    token_size: int

@dataclass
class SkillEntry:
    name: str
    description: str
    file_path: str
    tools: list[str]

@dataclass
class SkillSnapshot:
    version: int
    skills: list[SkillEntry]
    prompt: str

class SkillManager:
    def __init__(self):
        self._definitions: dict[str, SkillDefinition] = {}
        self._snapshot: Optional[SkillSnapshot] = None
        self._snapshot_version: int = 0

    def scan(self) -> None:
        """Scan SKILLS_DIR, parse YAML frontmatter from each SKILL.md."""
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            if skill_file.stat().st_size > MAX_SKILL_FILE_BYTES:
                continue
            content = skill_file.read_text(encoding="utf-8")
            meta = self._parse_frontmatter(content)
            if not meta:
                continue
            skill_id = meta.get("name", skill_dir.name)
            token_size = len(content) // 3
            self._definitions[skill_id] = SkillDefinition(
                id=skill_id,
                name=meta.get("name", skill_id),
                version=meta.get("version", "1.0.0"),
                description=meta.get("description", ""),
                file_path=str(skill_file).replace(str(Path.home()), "~"),
                tools=meta.get("tools", []),
                mutex_group=meta.get("mutex_group"),
                priority=meta.get("priority", 0),
                status=meta.get("status", "active"),
                disable_model_invocation=meta.get("disable-model-invocation", False),
                token_size=token_size,
            )

    def _parse_frontmatter(self, content: str) -> Optional[dict]:
        if not content.startswith("---"):
            return None
        end = content.find("---", 3)
        if end == -1:
            return None
        try:
            return yaml.safe_load(content[3:end])
        except Exception:
            return None

    def build_snapshot(self) -> SkillSnapshot:
        """Build SkillSnapshot from active, visible skills with 3-tier budget."""
        active = [
            d for d in self._definitions.values()
            if d.status == "active" and not d.disable_model_invocation
        ]
        active.sort(key=lambda x: -x.priority)

        entries = []
        total_chars = 195
        use_compact = False

        for d in active[:MAX_SKILLS_IN_PROMPT]:
            entry_chars = 97 + len(d.name) + len(d.description) + len(d.file_path)
            if total_chars + entry_chars > MAX_SKILLS_PROMPT_CHARS:
                use_compact = True
                break
            total_chars += entry_chars
            entries.append(SkillEntry(
                name=d.name,
                description=d.description,
                file_path=d.file_path,
                tools=d.tools,
            ))

        prompt = self._build_prompt(entries, compact=use_compact)
        self._snapshot_version += 1
        self._snapshot = SkillSnapshot(
            version=self._snapshot_version,
            skills=entries,
            prompt=prompt,
        )
        return self._snapshot

    def _build_prompt(self, entries: list[SkillEntry], compact: bool) -> str:
        if not entries:
            return ""
        if compact:
            lines = ["<skills>", "  ⚠️ skills directory (use read_file for details)"]
            for e in entries:
                lines += [f"  <skill><name>{e.name}</name><file_path>{e.file_path}</file_path></skill>"]
            lines.append("</skills>")
        else:
            lines = [
                "<skills>",
                "  The following skills provide task-specific operation guides.",
                "  When a task matches, use read_file to load the full guide.",
                "",
            ]
            for e in entries:
                tool_str = ", ".join(e.tools)
                lines += [
                    "  <skill>",
                    f"    <name>{e.name}</name>",
                    f"    <description>",
                    f"      {e.description}",
                    f"      depends on tools: {tool_str}",
                    f"    </description>",
                    f"    <file_path>{e.file_path}</file_path>",
                    "  </skill>",
                    "",
                ]
            lines.append("</skills>")
        return "\n".join(lines)

    def get_skill(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._definitions.get(skill_id)

    def read_skill_content(self, skill_id: str) -> str:
        d = self._definitions.get(skill_id)
        if not d:
            return f"[error] skill '{skill_id}' not found. available: {list(self._definitions.keys())}"
        path = d.file_path.replace("~", str(Path.home()))
        return Path(path).read_text(encoding="utf-8")

    def list_all(self) -> list[dict]:
        return [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "status": d.status,
                "tools": d.tools,
                "mutex_group": d.mutex_group,
                "priority": d.priority,
                "token_size": d.token_size,
                "file_path": d.file_path,
            }
            for d in self._definitions.values()
        ]

skill_manager = SkillManager()
```

### 5. skills/definitions/ — SKILL.md Files

Create 3 SKILL.md files. Each must contain full YAML frontmatter + `## Instructions` + `## Examples` sections.

**legal-search/SKILL.md:**
```markdown
---
name: legal-search
description: >
  Professional legal regulation retrieval and citation specialist.
  Trigger conditions: user mentions contract/signing/violation/compliance/legal terms;
  task involves legal text understanding or compliance risk assessment;
  user explicitly requests legal angle analysis.
  Mutex group: document-analysis
version: 1.0.0
status: active
mutex_group: document-analysis
priority: 10
disable-model-invocation: false
tools:
  - web_search
  - read_file
---

# Legal Search Skill

## Instructions

Step 1. Use web_search with keywords, restrict to site:npc.gov.cn or site:court.gov.cn
Step 2. Verify sources — non-official sites must be labeled "non-official, for reference only"
Step 3. Cite in format: 《Law Name》Article X (YYYY revision)
Step 4. If user follows up, repeat Step 1-3. Never cite from memory.

## Examples

Input: "What does Article 37 of the Labor Contract Law say?"
Output: "Per 《Labor Contract Law》Article 37 (2022 revision):
         Employees may terminate the labor contract by providing 30 days written notice.
         Source: NPC (npc.gov.cn)"

Input: "How is contract breach liability calculated?"
Output: "Contract breach liability calculation references the following:
         ..."
```

**csv-reporter/SKILL.md** and **contract-analyzer/SKILL.md** — implement similarly with domain-appropriate instructions.

### 6. tools/skill_tool.py
```python
from langchain_core.tools import tool
from skills.manager import skill_manager

@tool
def activate_skill(name: str) -> str:
    """
    Activate an Agent Skill to get the complete operation guide for this task type.
    Call when the task requires professional expertise (legal research, contract analysis, data reporting).
    Returns an operation manual. Read it and follow its instructions for subsequent steps.

    Args:
        name: skill name, e.g. "legal-search", "contract-analyzer", "csv-reporter"
    """
    return skill_manager.read_skill_content(name)
```

### 7. tools/web_search.py
```python
from langchain_core.tools import tool
from tavily import TavilyClient
from config import settings

tavily = TavilyClient(api_key=settings.tavily_api_key)

@tool
def web_search(query: str) -> str:
    """
    Search the internet for real-time information.
    Use for: latest regulations, current prices, recent news, anything post-2024.
    Do not use for: static knowledge, math calculations.
    """
    result = tavily.search(query=query, max_results=5)
    return "\n\n".join(
        f"[{r['title']}]({r['url']})\n{r['content']}"
        for r in result.get("results", [])
    )
```

### 8. tools/send_email.py (HIL mock tool)
```python
from langchain_core.tools import tool

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    Send an email notification. THIS IS AN IRREVERSIBLE OPERATION requiring human confirmation.
    Use for: contract signing reminders, overdue notifications, approval requests.
    This tool triggers a Human-in-the-Loop confirmation before execution.

    Args:
        to: recipient email address
        subject: email subject
        body: email body content
    """
    # Mock — does not actually send. HIL middleware intercepts before this runs.
    return f"[MOCK] Email sent to {to}: subject='{subject}'"
```

### 9. memory/schemas.py
```python
from pydantic import BaseModel
from typing import Optional

class EpisodicData(BaseModel):
    user_id: str = ""
    preferences: dict[str, str] = {}
    interaction_count: int = 0
    summary: str = ""

class MemoryContext(BaseModel):
    episodic: EpisodicData = EpisodicData()
```

### 10. memory/manager.py
```python
from langgraph.store.base import BaseStore
from memory.schemas import EpisodicData, MemoryContext

class MemoryManager:
    def __init__(self, store: BaseStore):
        self.store = store

    async def load_episodic(self, user_id: str) -> EpisodicData:
        item = await self.store.aget(
            namespace=("profile", user_id),
            key="episodic",
        )
        return EpisodicData(**item.value) if item else EpisodicData(user_id=user_id)

    async def save_episodic(self, user_id: str, data: EpisodicData) -> None:
        await self.store.aput(
            namespace=("profile", user_id),
            key="episodic",
            value=data.model_dump(),
        )

    def build_ephemeral_prompt(self, ctx: MemoryContext) -> str:
        if not ctx.episodic.preferences:
            return ""
        lines = [f"  {k}: {v}" for k, v in ctx.episodic.preferences.items()]
        return "\n\n[User Profile]\n" + "\n".join(lines)
```

### 11. agent/middleware/memory.py

Implement `MemoryMiddleware(AgentMiddleware)` with:
- `state_schema = MemoryState` (TypedDict with `memory_ctx` field)
- `abefore_agent`: load EpisodicData from store → state["memory_ctx"]
- `wrap_model_call`: Ephemeral inject user profile into system_message via `request.override()`
- `aafter_agent`: increment interaction_count, extract domain from message content (keywords: contract/signing → legal-tech; csv/data → analytics), save back

### 12. agent/middleware/trace.py

Implement `TraceMiddleware(AgentMiddleware)` that:
- `after_model`: parse AIMessage content_blocks, extract thought text and tool_calls
- Emit SSE events: `thought`, `tool_start`, `tool_result`
- Also build and emit `context_window` event with full TokenBudgetState after every LLM call
- Write AgentTrace to `agent_traces` table

### 13. agent/langchain_engine.py
```python
from langchain.agents import create_agent
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from agent.middleware.memory import MemoryMiddleware
from agent.middleware.trace import TraceMiddleware
from tools.registry import get_all_tools
from skills.manager import skill_manager
from prompt.builder import build_system_prompt
from config import settings

def llm_factory():
    if settings.llm_provider == "anthropic":
        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
        )
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )

async def build_agent(checkpointer, store, memory_manager):
    # Ensure skills are scanned and snapshot built
    skill_manager.scan()
    snapshot = skill_manager.build_snapshot()
    system_prompt = build_system_prompt(skill_snapshot=snapshot)

    agent = create_agent(
        model=llm_factory(),
        tools=get_all_tools(),
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        store=store,
        middleware=[
            MemoryMiddleware(memory_manager),
            TraceMiddleware(),
            SummarizationMiddleware(
                model=llm_factory(),
                trigger=("fraction", 0.75),
                keep=("messages", 5),
            ),
        ],
    )
    return agent
```

### 14. prompt/builder.py

Build system prompt including:
1. Role definition
2. Capabilities and constraints
3. Skill Protocol (4 rules: when/how/execute/conflict)
4. SkillSnapshot.prompt (injected from SkillManager)
5. Static few-shot examples (E-signature platform scenarios)
6. Output format rules

The Skill Protocol must include all 4 rules:
- When: activate when user request matches skill description
- How: call `read_file(path=<file_path from snapshot>)`. Never execute from memory.
- Execute: follow ## Instructions strictly; match ## Examples format
- Conflict: same mutex_group → activate only highest priority; only 1 skill per turn

### 15. main.py — FastAPI with SSE
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, asyncio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: str = "dev_user"

class ResumeRequest(BaseModel):
    session_id: str
    interrupt_id: str
    action: str  # "approve" | "reject"

@app.post("/chat")
async def chat(req: ChatRequest):
    """Main chat endpoint with SSE streaming."""
    async def event_generator():
        try:
            async for stream_mode, data in agent.astream(
                {"messages": [{"role": "user", "content": req.message}]},
                config={
                    "configurable": {
                        "thread_id": req.session_id,
                        "user_id": req.user_id,
                    }
                },
                stream_mode=["messages", "updates"],
            ):
                if stream_mode == "messages":
                    token, metadata = data
                    # AIMessageChunk streaming
                    if hasattr(token, "content") and token.content:
                        text = token.content if isinstance(token.content, str) else ""
                        if text:
                            yield f"event: thought\ndata: {json.dumps({'text': text})}\n\n"
                    if hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
                        yield f"event: tool_start\ndata: {json.dumps({'chunks': token.tool_call_chunks})}\n\n"

                elif stream_mode == "updates":
                    for source, update in data.items():
                        if source == "tools":
                            msgs = update.get("messages", [])
                            if msgs:
                                result = msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
                                yield f"event: tool_result\ndata: {json.dumps({'result': result})}\n\n"
                        if source == "__interrupt__":
                            interrupt_data = update[0].value if update else {}
                            yield f"event: hil_interrupt\ndata: {json.dumps(interrupt_data)}\n\n"

            yield f"event: done\ndata: {{}}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/chat/resume")
async def chat_resume(req: ResumeRequest):
    """Resume after HIL confirmation."""
    # Restore checkpoint and continue or inject rejection tool message
    ...

@app.get("/skills")
async def list_skills():
    return {"skills": skill_manager.list_all()}

@app.get("/skills/{skill_id}/content")
async def get_skill_content(skill_id: str):
    content = skill_manager.read_skill_content(skill_id)
    return {"skill_id": skill_id, "content": content}

@app.get("/session/{session_id}/context")
async def get_context_window(session_id: str):
    """Return current TokenBudgetState for a session."""
    # Look up the latest token budget state from in-memory store
    ...

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 16. supabase/migrations/0001_init.sql
```sql
create table if not exists agent_traces (
    id            uuid        primary key default gen_random_uuid(),
    session_id    text        not null,
    user_id       text        not null default 'dev_user',
    user_input    text,
    final_answer  text,
    thought_chain jsonb       not null default '[]',
    tool_calls    jsonb       not null default '[]',
    token_usage   jsonb       not null default '{}',
    latency_ms    integer,
    finish_reason text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_traces_session on agent_traces(session_id);
create index if not exists idx_traces_user on agent_traces(user_id);
```

---

## Frontend Implementation

### Design Principles
- Three-panel layout: left sidebar (Skills), center (Chat), right sidebar (Context Window)
- ReAct chain renders inline below each AI message as collapsible steps
- Token Context Window panel is always visible on the right
- Dark/light mode support via CSS variables
- Beautiful, minimal design — inspired by linear.app aesthetics
- Use shadcn/ui for all form elements, dialogs, badges

### Layout: app/page.tsx

Three-column grid layout:
```
┌──────────────────────────────────────────────────────────────┐
│  Header: logo + session id + model badge + status indicator  │
├───────────────┬───────────────────────┬──────────────────────┤
│  Skills Panel │    Chat Panel         │  Context Window      │
│  (280px)      │    (flex-1)           │  Panel (320px)       │
│               │                       │                      │
│  SkillCard×3  │  MessageList          │  TokenBudget viz     │
│               │  + ReActTrace         │  SlotBars            │
│  Active badge │  (inline per msg)     │  CompressionLog      │
│               │                       │  Stats cards         │
│  Click →      │  InputBar             │                      │
│  SkillDetail  │  + HIL dialog         │                      │
└───────────────┴───────────────────────┴──────────────────────┘
```

### components/chat/MessageItem.tsx

Each AI message renders:
1. The text response with markdown rendering
2. A collapsible `<ReActPanel>` below it showing the full chain for that turn

### components/react-trace/ReActPanel.tsx

Renders the complete ReAct chain for one agent turn as a vertical timeline:
```
┌─ ReAct Trace · Turn 3 ──────────────────────── 4.2s ─┐
│                                                        │
│  ● Thought                                    0.8s    │
│    User is asking about legal compliance...            │
│                                                        │
│  ▶ Tool Call · activate_skill                 0.2s    │
│    args: { name: "legal-search" }                      │
│    ┌─ Result ──────────────────────────────────┐      │
│    │ # Legal Search Skill                       │      │
│    │ ## Instructions                            │      │
│    │ Step 1. Use web_search...                  │      │
│    └───────────────────────────────────────────┘      │
│                                                        │
│  ● Thought                                    0.6s    │
│    I have the legal-search skill. Now I'll...          │
│                                                        │
│  ▶ Tool Call · web_search                     1.8s    │
│    args: { query: "电子签名法 2024 site:npc.gov.cn" } │
│    ┌─ Result ──────────────────────────────────┐      │
│    │ [电子签名法] ...                            │      │
│    └───────────────────────────────────────────┘      │
│                                                        │
│  ■ Final Answer                               0.8s    │
└────────────────────────────────────────────────────────┘
```

Each step has a color-coded left border:
- Thought: purple
- Tool Call: blue
- Tool Result: teal
- Final Answer: green
- HIL Interrupt: amber

Use Framer Motion for staggered entry animation of each step as SSE events arrive.

### components/context-window/ContextWindowPanel.tsx

Exact reference: the token context visualization widget shown in this conversation.

Implement all 4 sections:
1. **Overall progress bar** — segmented bar with colored regions per slot, percentage used
2. **Slot breakdown table** — slot number, color dot, name, mini bar, used/max tokens, overflow warning
3. **Compression events log** — each compression as a card with before/after token counts
4. **Stats row** — total turns, total tokens saved, active skill name

Update in real time via SSE `context_window` events. Each event carries the full `TokenBudgetState` JSON.

Slot colors (match the design shown in this conversation):
- ① System Prompt: purple (#534AB7)
- ② Active Skill: dark purple (#3C3489)
- ③ Dynamic Few-shot: dark teal (#0F6E56)
- ④ RAG Context: disabled gray
- ⑤ User Profile: teal (#1D9E75)
- ⑦ Tool Schemas: blue (#185FA5)
- ⑧ Conversation History: light blue (#378ADD)
- ⑩ Current Input: pale blue (#B5D4F4)

Show overflow badge (⚠) in amber when a slot exceeds its budget.

### components/skills/SkillPanel.tsx

Left sidebar showing all registered skills:
```
┌─ Skills ──────────────────────────────────┐
│                                           │
│  ┌─ legal-search ──────────── ACTIVE ──┐ │
│  │ Legal regulation retrieval         │ │
│  │ tools: web_search, read_file       │ │
│  │ priority: 10 · mutex: doc-analysis │ │
│  └────────────────────────────────────┘ │
│                                           │
│  ┌─ csv-reporter ──────────── active ──┐ │
│  │ CSV data analysis and reporting    │ │
│  └────────────────────────────────────┘ │
│                                           │
│  ┌─ contract-analyzer ───── disabled ──┐ │
│  │ Contract clause risk analysis      │ │
│  └────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

Click a skill card → show `SkillDetail` drawer/sheet with:
- Full SKILL.md rendered as markdown
- Token size badge
- Activation history in current session
- "Currently active" indicator when it's in context

`ACTIVE` badge (green) appears when a skill's ToolMessage is present in the current session's conversation history.

### components/hil/HILConfirmDialog.tsx

Full-screen modal overlay (using shadcn Dialog) that appears when `hil_interrupt` SSE event fires:
```
┌─────────────────────────────────────────────────────────┐
│  ⚠  Action requires confirmation                         │
│                                                         │
│  The agent is about to perform an irreversible action:  │
│                                                         │
│  Tool:    send_email                                    │
│  To:      boss@company.com                             │
│  Subject: Q3 Contract Status Report                    │
│  Body:    "Dear..., here is the summary..."            │
│                                                         │
│  This will send a real email and cannot be undone.     │
│                                                         │
│  ┌──────────────┐  ┌─────────────────────────────────┐ │
│  │  ✕ Cancel    │  │  ✓ Confirm and Execute          │ │
│  └──────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### hooks/useSSE.ts
```typescript
import { useEffect, useRef, useCallback } from "react";

export type SSEEvent =
  | { type: "thought"; text: string }
  | { type: "tool_start"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; result: string }
  | { type: "context_window"; data: TokenBudgetState }
  | { type: "hil_interrupt"; interrupt_id: string; tool_name: string; tool_args: Record<string, unknown> }
  | { type: "done" }
  | { type: "error"; message: string };

export function useSSE(onEvent: (event: SSEEvent) => void) {
  // implement EventSource connection, auto-reconnect, cleanup
}
```

### types/index.ts

Define all TypeScript interfaces matching backend Pydantic models:
- `TokenBudgetState`, `SlotUsage`, `CompressionEvent`
- `SkillDefinition`, `SkillSnapshot`
- `ReActStep`, `ReActTrace`
- `Message`, `ChatSession`
- `HILInterrupt`

---

## E2E Tests (Playwright)

### playwright.config.ts
```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  retries: 1,
  workers: 1,
  reporter: [
    ["html", { open: "on-failure" }],
    ["list"],
  ],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "on",
    video: "retain-on-failure",
    // HEADED mode — user can see the browser
    headless: false,
    slowMo: 300,          // 300ms delay so human can follow along
    viewport: { width: 1440, height: 900 },
  },
  webServer: [
    {
      command: "cd backend && uvicorn main:app --port 8000",
      port: 8000,
      reuseExistingServer: true,
    },
    {
      command: "cd frontend && npm run dev",
      port: 3000,
      reuseExistingServer: true,
    },
  ],
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

### tests/e2e/chat.spec.ts

Cover:
1. Page load — all 3 panels visible
2. Send a message — SSE streaming starts, thought bubbles appear progressively
3. Tool call triggers — ToolCallStep card renders with correct tool name and args
4. Final answer — message complete, done event fires
5. Session persistence — refresh page, previous messages reload from checkpointer
6. Second turn — agent remembers context from first turn

### tests/e2e/react-trace.spec.ts

Cover:
1. ReActPanel renders below each AI message
2. Thought steps show purple left border
3. Tool call steps show blue left border with expandable args
4. Tool result steps show teal left border with collapsible content
5. Step timing badges show correct ms values
6. Collapse/expand animation works
7. Multi-tool turn shows correct step ordering

### tests/e2e/context-window.spec.ts

Cover:
1. ContextWindowPanel visible on right sidebar
2. Overall progress bar updates after each message
3. All slot rows render with correct labels
4. Slot overflow shows amber warning badge
5. Compression event appears in log when triggered
6. Stats cards update (turns, tokens saved, active skill)
7. Verify slot colors match design spec

### tests/e2e/skills.spec.ts

Cover:
1. SkillPanel renders all 3 skills
2. Status badges correct (active/disabled)
3. Click skill → SkillDetail drawer opens with SKILL.md content rendered
4. Send message that triggers legal-search skill:
   - Message: "Does this e-signature contract have legal validity?"
   - Assert: activate_skill tool call appears in ReActPanel
   - Assert: legal-search SKILL.md content appears in tool result
   - Assert: legal-search skill card shows ACTIVE badge
5. After skill activation, ContextWindowPanel slot ② shows legal-search token count
6. Second message reuses skill (no duplicate activate_skill call per Protocol rule ①)

### tests/e2e/hil.spec.ts

Cover:
1. Send message that triggers send_email: "Search for contract status and email my manager"
2. HILConfirmDialog appears (modal overlay visible)
3. Dialog shows correct tool_args (to, subject, body)
4. Click Cancel → agent receives rejection, replies with cancellation message
5. Repeat, click Confirm → send_email executes, success message appears
6. ContextWindowPanel updates during both flows
7. Session checkpoint preserves state across HIL pause

---

## Docker Setup

### docker-compose.yml
```yaml
version: "3.8"
services:
  db:
    image: supabase/postgres:15.1.0.117
    ports:
      - "54322:5432"
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/supabase/migrations:/docker-entrypoint-initdb.d

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on: [db]
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    env_file: .env
    depends_on: [backend]

volumes:
  pgdata:
```

---

## Implementation Notes

1. **SkillManager is the critical module** — all 3-tier budget logic (full → compact → bisect) must be implemented. The Skill Protocol text must be injected into system prompt verbatim with all 4 rules.

2. **SSE event taxonomy** — backend must emit exactly these event types:
   `thought`, `tool_start`, `tool_result`, `context_window`, `hil_interrupt`, `done`, `error`

3. **context_window event** — emit after EVERY LLM call with updated `TokenBudgetState`. Frontend ContextWindowPanel subscribes and re-renders on each event.

4. **Playwright headed mode** — `headless: false` + `slowMo: 300` is mandatory. User must see the browser executing tests.

5. **Token counting** — use character-based approximation for P0. Track ALL 10 slots. Update slot ② (active skill) to the token size of the loaded SKILL.md whenever activate_skill fires.

6. **Ephemeral injection** — user profile is injected via `request.override(system_message=...)` in `wrap_model_call`. It must NOT appear in `state["messages"]` or checkpoint history.

7. **HIL** — `send_email` tool is in `interrupt_on` list for `HumanInTheLoopMiddleware`. The `/chat/resume` endpoint restores from checkpoint. Never re-run preceding tool calls.

8. **UI beauty** — use shadcn/ui components throughout. Framer Motion for ReAct step animations. The Context Window panel must exactly match the slot color scheme specified above. Typography: Inter/Geist font, clean spacing.

9. **Test coverage** — every test must use `await page.waitForSelector()` with appropriate timeouts (SSE can take 5-15s). Screenshot on failure. All 5 spec files must run `npx playwright test --headed`.

10. **Start order** — `docker-compose up db`, then run `python -c "from db.postgres import create_stores; import asyncio; asyncio.run(create_stores())"` for migrations, then start backend and frontend.

---

## Deliverable Checklist

- [ ] All SKILL.md files with valid frontmatter + Instructions + Examples
- [ ] SkillManager with scan(), build_snapshot(), 3-tier budget, read_skill_content()
- [ ] Skill Protocol injected into system prompt (all 4 rules)
- [ ] activate_skill @tool working end-to-end
- [ ] TokenBudgetState tracking all 10 slots + compression events
- [ ] SSE `context_window` event emitted after every LLM call
- [ ] ReActPanel with color-coded steps + Framer Motion animations
- [ ] ContextWindowPanel with segmented bar, slot rows, compression log
- [ ] SkillPanel with status badges + SkillDetail drawer
- [ ] HILConfirmDialog with approve/reject flows
- [ ] Playwright config with `headless: false`, `slowMo: 300`
- [ ] All 5 e2e spec files with assertions
- [ ] docker-compose.yml working
- [ ] README with setup instructions