"""测试 create_react_agent 在 context_window 后发出 session_metadata SSE 事件。"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_session_metadata_event_emitted():
    """create_react_agent 应发出含 model/session_name/created_at 的 session_metadata 事件。"""
    from app.agent.langchain_engine import create_react_agent

    events = []

    async def fake_queue_put(queue, item):
        events.append(item)

    with patch('app.agent.langchain_engine._queue_put', side_effect=fake_queue_put), \
         patch('app.agent.langchain_engine.llm_factory', return_value=MagicMock()), \
         patch('app.agent.langchain_engine.build_tool_registry',
               return_value=([], MagicMock(), MagicMock())), \
         patch('app.agent.langchain_engine.SkillManager.get_instance') as mock_sm, \
         patch('app.agent.langchain_engine.build_system_prompt') as mock_bsp, \
         patch('app.agent.langchain_engine.create_summarization_middleware',
               return_value=MagicMock()), \
         patch('app.agent.langchain_engine.create_agent', return_value=MagicMock()):

        mock_slot = MagicMock()
        mock_slot.to_dict.return_value = {'slots': []}
        mock_slot.total_tokens = 0
        mock_sm.return_value.build_snapshot.return_value = MagicMock(
            skills=[], version=1, total_tokens=0
        )
        mock_bsp.return_value = ('', mock_slot)

        queue = MagicMock()
        await create_react_agent(sse_queue=queue)

    event_types = [e[0] for e in events]
    assert 'session_metadata' in event_types, f"Expected session_metadata in {event_types}"

    meta_payload = next(e[1] for e in events if e[0] == 'session_metadata')
    assert 'model' in meta_payload, "session_metadata must contain 'model'"
    assert 'session_name' in meta_payload, "session_metadata must contain 'session_name'"
    assert 'created_at' in meta_payload, "session_metadata must contain 'created_at'"
