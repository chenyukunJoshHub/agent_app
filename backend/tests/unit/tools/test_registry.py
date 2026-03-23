"""Test ToolRegistry - RED phase.

Per architecture doc §2.1:
- ToolRegistry provides centralized tool registration
- Tools are registered with unique names
- get_all() returns list of BaseTool instances
- get_by_name() retrieves tool by name or raises KeyError
- register() prevents duplicate tool names
"""
import pytest
from unittest.mock import Mock

from langchain_core.tools import BaseTool, tool

from app.tools.registry import ToolRegistry


class TestToolRegistryRegister:
    """Test ToolRegistry.register() method."""

    def test_register_single_tool(self):
        """验证注册单个工具成功"""
        registry = ToolRegistry()

        @tool
        def test_tool() -> str:
            """Test tool."""
            return "test"

        registry.register(test_tool)
        assert len(registry.get_all()) == 1
        assert registry.get_all()[0].name == "test_tool"

    def test_register_multiple_tools(self):
        """验证注册多个工具成功"""
        registry = ToolRegistry()

        @tool
        def tool_one() -> str:
            """Tool one."""
            return "one"

        @tool
        def tool_two() -> str:
            """Tool two."""
            return "two"

        registry.register(tool_one)
        registry.register(tool_two)

        tools = registry.get_all()
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "tool_one" in tool_names
        assert "tool_two" in tool_names

    def test_register_duplicate_tool_name_raises_error(self):
        """验证重复注册同名工具时抛出 ValueError"""
        registry = ToolRegistry()

        @tool
        def duplicate_tool() -> str:
            """Duplicate tool."""
            return "first"

        registry.register(duplicate_tool)

        # 尝试注册同名工具
        @tool
        def duplicate_tool() -> str:  # noqa: F811
            """Another duplicate tool."""
            return "second"

        with pytest.raises(ValueError, match="already registered"):
            registry.register(duplicate_tool)

    def test_register_returns_tool_name(self):
        """验证 register() 返回工具名称"""
        registry = ToolRegistry()

        @tool
        def named_tool() -> str:
            """Named tool."""
            return "result"

        name = registry.register(named_tool)
        assert name == "named_tool"


class TestToolRegistryGetAll:
    """Test ToolRegistry.get_all() method."""

    def test_get_all_returns_empty_list_initially(self):
        """验证初始状态下 get_all() 返回空列表"""
        registry = ToolRegistry()
        tools = registry.get_all()
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_get_all_returns_list_of_base_tools(self):
        """验证 get_all() 返回 BaseTool 实例列表"""
        registry = ToolRegistry()

        @tool
        def example_tool() -> str:
            """Example tool."""
            return "example"

        registry.register(example_tool)
        tools = registry.get_all()

        assert len(tools) == 1
        assert isinstance(tools[0], BaseTool)

    def test_get_all_returns_tools_in_registration_order(self):
        """验证 get_all() 按注册顺序返回工具"""
        registry = ToolRegistry()

        @tool
        def first_tool() -> str:
            """First tool."""
            return "first"

        @tool
        def second_tool() -> str:
            """Second tool."""
            return "second"

        @tool
        def third_tool() -> str:
            """Third tool."""
            return "third"

        registry.register(first_tool)
        registry.register(second_tool)
        registry.register(third_tool)

        tools = registry.get_all()
        assert [t.name for t in tools] == ["first_tool", "second_tool", "third_tool"]

    def test_get_all_returns_independent_list(self):
        """验证 get_all() 返回独立列表，修改不影响内部状态"""
        registry = ToolRegistry()

        @tool
        def test_tool() -> str:
            """Test tool."""
            return "test"

        registry.register(test_tool)
        tools = registry.get_all()

        # 尝试修改返回的列表
        tools.clear()

        # 再次获取应该仍然包含工具
        tools_again = registry.get_all()
        assert len(tools_again) == 1


class TestToolRegistryGetByName:
    """Test ToolRegistry.get_by_name() method."""

    def test_get_by_name_returns_correct_tool(self):
        """验证 get_by_name() 返回正确的工具"""
        registry = ToolRegistry()

        @tool
        def specific_tool_func() -> str:
            """Specific tool."""
            return "specific"

        registry.register(specific_tool_func)
        retrieved_tool = registry.get_by_name("specific_tool_func")

        assert isinstance(retrieved_tool, BaseTool)
        assert retrieved_tool.name == "specific_tool_func"

    def test_get_by_name_raises_keyerror_for_unknown_tool(self):
        """验证获取不存在的工具时抛出 KeyError"""
        registry = ToolRegistry()

        with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
            registry.get_by_name("nonexistent")

    def test_get_by_name_with_multiple_tools(self):
        """验证在多个工具中正确获取指定工具"""
        registry = ToolRegistry()

        @tool
        def tool_a() -> str:
            """Tool A."""
            return "a"

        @tool
        def tool_b() -> str:
            """Tool B."""
            return "b"

        @tool
        def tool_c() -> str:
            """Tool C."""
            return "c"

        registry.register(tool_a)
        registry.register(tool_b)
        registry.register(tool_c)

        retrieved_tool = registry.get_by_name("tool_b")
        assert retrieved_tool.name == "tool_b"

    def test_get_by_name_case_sensitive(self):
        """验证工具名称区分大小写"""
        registry = ToolRegistry()

        @tool
        def MyToolFunc() -> str:
            """MyTool."""
            return "my"

        registry.register(MyToolFunc)

        # 应该能获取到正确的大小写
        retrieved_tool = registry.get_by_name("MyToolFunc")
        assert retrieved_tool.name == "MyToolFunc"

        # 错误的大小写应该抛出 KeyError
        with pytest.raises(KeyError):
            registry.get_by_name("mytoolfunc")


class TestToolRegistryIntegration:
    """Test ToolRegistry integration with existing tools."""

    def test_register_web_search_tool(self):
        """验证注册 web_search 工具"""
        from app.tools.search import web_search

        registry = ToolRegistry()
        name = registry.register(web_search)

        assert name == "web_search"
        tools = registry.get_all()
        assert len(tools) == 1
        assert tools[0].name == "web_search"

    def test_register_read_file_tool(self):
        """验证注册 read_file 工具"""
        from app.tools.file import read_file

        registry = ToolRegistry()
        name = registry.register(read_file)

        assert name == "read_file"
        tools = registry.get_all()
        assert len(tools) == 1

    def test_register_multiple_existing_tools(self):
        """验证注册多个现有工具"""
        from app.tools.search import web_search
        from app.tools.file import read_file

        registry = ToolRegistry()
        registry.register(web_search)
        registry.register(read_file)

        tools = registry.get_all()
        tool_names = [t.name for t in tools]
        assert "web_search" in tool_names
        assert "read_file" in tool_names

    def test_get_by_name_retrieves_web_search(self):
        """验证通过名称获取 web_search 工具"""
        from app.tools.search import web_search

        registry = ToolRegistry()
        registry.register(web_search)

        retrieved_tool = registry.get_by_name("web_search")
        assert retrieved_tool.name == "web_search"
        # 验证工具的内部函数可调用 (StructuredTool 本身不是 callable)
        assert hasattr(retrieved_tool, "func")
        assert callable(retrieved_tool.func)


class TestToolRegistryEdgeCases:
    """Test ToolRegistry edge cases and error handling."""

    def test_register_none_raises_error(self):
        """验证注册 None 时抛出错误"""
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="Tool cannot be None"):
            registry.register(None)  # type: ignore

    def test_register_non_base_tool_raises_error(self):
        """验证注册非 BaseTool 对象时抛出错误"""
        registry = ToolRegistry()

        class NotATool:
            pass

        with pytest.raises(ValueError, match="must be a BaseTool"):
            registry.register(NotATool())  # type: ignore

    def test_get_by_name_empty_string(self):
        """验证使用空字符串获取工具时抛出 KeyError"""
        registry = ToolRegistry()

        with pytest.raises(KeyError):
            registry.get_by_name("")


class TestToolRegistryAdditionalMethods:
    """Test additional ToolRegistry methods."""

    def test_unregister_removes_tool(self):
        """验证 unregister() 移除工具"""
        registry = ToolRegistry()

        @tool
        def temp_tool() -> str:
            """Temp tool."""
            return "temp"

        registry.register(temp_tool)
        assert len(registry) == 1

        registry.unregister("temp_tool")
        assert len(registry) == 0

    def test_unregister_nonexistent_tool_raises_error(self):
        """验证 unregister 不存在的工具时抛出 KeyError"""
        registry = ToolRegistry()

        with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
            registry.unregister("nonexistent")

    def test_clear_removes_all_tools(self):
        """验证 clear() 移除所有工具"""
        registry = ToolRegistry()

        @tool
        def tool1() -> str:
            """Tool 1."""
            return "1"

        @tool
        def tool2() -> str:
            """Tool 2."""
            return "2"

        registry.register(tool1)
        registry.register(tool2)
        assert len(registry) == 2

        registry.clear()
        assert len(registry) == 0

    def test_len_returns_tool_count(self):
        """验证 __len__() 返回工具数量"""
        registry = ToolRegistry()

        @tool
        def tool_a() -> str:
            """Tool A."""
            return "a"

        @tool
        def tool_b() -> str:
            """Tool B."""
            return "b"

        assert len(registry) == 0

        registry.register(tool_a)
        assert len(registry) == 1

        registry.register(tool_b)
        assert len(registry) == 2

    def test_contains_checks_tool_existence(self):
        """验证 __contains__() 检查工具是否存在"""
        registry = ToolRegistry()

        @tool
        def existing_tool() -> str:
            """Existing tool."""
            return "exists"

        registry.register(existing_tool)

        assert "existing_tool" in registry
        assert "nonexistent_tool" not in registry
