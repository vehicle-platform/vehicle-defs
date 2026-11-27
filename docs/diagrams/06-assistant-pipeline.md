# Rider Assistant `/chat` Pipeline

**Caption:** Fixed single-tool execution pipeline of `POST /chat` in `vehicle-server` (D-121, D-127, D-128): refusal guard before routing, deterministic follow-up / symptom / keyword routing with LLM planner fallback, read-only `vehicle-mcp` tool call, template-first rendering or LLM verbalization checked by the number/output filter.

```mermaid
sequenceDiagram
  autonumber
  participant Client as vehicle-mobile / API Client
  participant Svc as ChatService<br/>(chat/service.py)
  participant Guard as Refusal Guard<br/>(chat/guard.py)
  participant Router as Follow-up, Router & Planner<br/>(followup.py, router.py, planner.py)
  participant MCP as vehicle-mcp ToolRunner<br/>(read-only stdio pool)
  participant LLM as Local llama-server / User Provider<br/>(chat/providers/)
  participant Filter as Template & Output Filter<br/>(answers.py, numbers.py, templates.py)

  Client->>Svc: POST /chat {message, locale, session_id, conversation_id}
  Svc->>Guard: refuses(message)?
  alt Asks to disable safety or modify/clear ECU
    Guard-->>Svc: true (invariants 1 & 3)
    Svc-->>Client: Fixed refusal template (source="template", no tool/LLM call)
  else Allowed question
    Svc->>Router: followup.resolve() -> pre_llm check_symptom -> deterministic router / LLM choose_tool -> topic card fallback
    Router-->>Svc: Plan(tool, arguments, focus)
    Svc->>MCP: call_tool(plan.tool, plan.arguments)
    MCP-->>Svc: labelled JSON result (no LLM math)

    alt Template-first eligible (not answers.uses_llm(plan, result))
      Svc->>Filter: answers.render(plan, result, locale)
      Filter-->>Svc: formatted text
      Svc-->>Client: ChatResponse (source="template", model=null, chips, new_state)
    else LLM verbalization path
      Svc->>Svc: format_result() + budget.assemble() (fixed prefix + context)
      Svc->>LLM: phrase(system_prompt, context + labelled result)
      LLM-->>Svc: draft answer + timings (prompt_n, cache_n)
      Svc->>Filter: len <= 1200 && answers.output_ok(text, result, locale)?
      alt Passes number guard & output filter
        Filter-->>Svc: OK
        Svc-->>Client: ChatResponse (source="llm", model=reported, chips, new_state)
      else Rejected or provider error
        Filter-->>Svc: rejected -> deterministic template fallback
        Svc-->>Client: ChatResponse (source="template", model=null, chips, new_state)
      end
    end
  end
```

## Sources
- `vehicle-defs/docs/DECISIONS.md`: D-121 (LLM only verbalizes, single read-only MCP tool, number guard, template fallback), D-124 (optional per-user cloud provider with local fallback), D-127 (answering model visible, deterministic symptom check, labelled results), D-128 (stored conversations, code-carried follow-ups, memory commands, chips)
- `vehicle-server/src/vehicle_server/chat/service.py` (`ChatService.answer`, `_run`, `_choose`, `_symptom_step`, `_topic_card`, `_phrase`, `format_result`)
- `vehicle-server/src/vehicle_server/chat/guard.py` (`refuses`)
