"""
Simple test script to verify backend components without database
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))


def test_config():
    """Test configuration loading"""
    print("🔧 Testing configuration...")
    try:
        from app.core.config import settings
        print(f"  ✓ App: {settings.app_name} v{settings.app_version}")
        print(f"  ✓ LLM Provider: {settings.llm_provider}")
        print(f"  ✓ Default Model: {settings.default_model}")
        return True
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return False


def test_logger():
    """Test logger setup"""
    print("\n📝 Testing logger...")
    try:
        from app.core.logger import loguru_logger
        loguru_logger.info("Test log message")
        print("  ✓ Logger initialized")
        return True
    except Exception as e:
        print(f"  ✗ Logger error: {e}")
        return False


def test_llm_factory():
    """Test LLM Factory"""
    print("\n🤖 Testing LLM Factory...")
    try:
        from app.llm.factory import llm_factory

        # Test factory creation (won't call API without key)
        llm = llm_factory.create_langchain_llm()
        print(f"  ✓ LLM created: {type(llm).__name__}")
        return True
    except Exception as e:
        print(f"  ✗ LLM Factory error: {e}")
        return False


def test_tools():
    """Test tool registry"""
    print("\n🔧 Testing Tools...")
    try:
        from app.tools.registry import tool_registry

        # Import to trigger registration
        import app.tools.builtin  # noqa: F401

        tools = tool_registry.list_all()
        print(f"  ✓ Registered tools: {list(tools.keys())}")
        print(f"  ✓ Tool count: {len(tools)}")
        return True
    except Exception as e:
        print(f"  ✗ Tools error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_executor():
    """Test Agent Executor (without database)"""
    print("\n🤖 Testing Agent Executor...")
    try:
        from app.agent.executor import AgentExecutor

        executor = AgentExecutor()
        print(f"  ✓ Executor created: session_id={executor.session_id}")
        print(f"  ✓ Tools loaded: {len(executor._tools)}")
        return True
    except Exception as e:
        print(f"  ✗ Executor error: {e}")
        return False


def test_api_routes():
    """Test API routes"""
    print("\n🌐 Testing API Routes...")
    try:
        from app.api.main import app

        routes = [route.path for route in app.routes]
        api_routes = [r for r in routes if r.startswith("/api")]
        print(f"  ✓ API routes: {api_routes}")
        return True
    except Exception as e:
        print(f"  ✗ API routes error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Multi-Tool AI Agent - Component Tests")
    print("=" * 60)

    results = {
        "Config": test_config(),
        "Logger": test_logger(),
        "LLM Factory": test_llm_factory(),
        "Tools": test_tools(),
        "Agent Executor": test_agent_executor(),
        "API Routes": test_api_routes(),
    }

    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print("=" * 60)

    passed = sum(results.values())
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
