from typing import Literal

from pydantic import BaseModel, Field


class TestPoint(BaseModel):
    """测试点结构化定义。"""

    name: str = Field(description="测试点名称")
    test_type: Literal["功能", "性能", "安全", "兼容性"] = Field(
        description="测试类型，可选值：功能/性能/安全/兼容性"
    )
    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        description="测试点优先级，可选值：P0/P1/P2/P3"
    )


class TestCase(BaseModel):
    """测试用例结构化定义。"""

    case_id: str = Field(description="用例编号")
    directory: str = Field(description="用例所属目录")
    case_level: Literal["P0", "P1", "P2", "P3"] = Field(
        description="用例级别，可选值：P0/P1/P2/P3"
    )
    test_point: str = Field(description="测试点")
    precondition: str = Field(description="前提条件")
    steps: list[str] = Field(description="测试步骤列表，按执行顺序填写")
    expected_result: str = Field(description="预期结果")


class TestOutline(BaseModel):
    """测试大纲结构化定义。"""

    module_name: str = Field(description="模块名称")
    test_points: list[TestPoint] = Field(description="该模块下的测试点列表")
