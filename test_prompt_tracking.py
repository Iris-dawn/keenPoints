#!/usr/bin/env python3
"""Test script for prompt tracking functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.logger import log_llm_call, query_prompts, get_prompt_detail, get_prompt_stats
from app.core.config import set_current_paper

def test_logging():
    """Test basic logging functionality."""
    print("=== 测试 Prompt 日志记录 ===")
    
    # 设置当前论文
    set_current_paper("test_paper")
    
    # 模拟几个不同步骤的 LLM 调用
    test_cases = [
        {
            "llm_id": 2,
            "prompt": "分析这张图片的内容",
            "tag": "visual_image_1",
            "metadata": {
                "step": 2,
                "element_type": "image",
                "element_id": 1,
                "section_name": "3. Method"
            }
        },
        {
            "llm_id": 3,
            "prompt": "为这个章节生成 PPT 大纲",
            "tag": "outline_1",
            "metadata": {
                "step": 3,
                "section_name": "3. Method"
            }
        },
        {
            "llm_id": 4,
            "prompt": "生成 HTML 幻灯片",
            "tag": "slide_01_text_only",
            "metadata": {
                "step": 7,
                "slide_id": 1,
                "slide_title": "System Architecture",
                "layout": "text_only"
            }
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}] 记录 LLM 调用: llm_id={case['llm_id']}, tag={case['tag']}")
        log_llm_call(
            llm_id=case["llm_id"],
            prompt=case["prompt"],
            response={"test": f"response_{i}"},
            tag=case["tag"],
            metadata=case["metadata"]
        )
    
    print("\n✓ 日志记录完成")


def test_query():
    """Test query functionality."""
    print("\n=== 测试 Prompt 查询 ===")
    
    # 查询所有
    print("\n[1] 查询所有记录:")
    results = query_prompts(limit=10)
    print(f"   找到 {len(results)} 条记录")
    
    # 按步骤查询
    print("\n[2] 查询 Step 2 的记录:")
    results = query_prompts(step=2, limit=10)
    print(f"   找到 {len(results)} 条记录")
    
    # 按 LLM ID 查询
    print("\n[3] 查询 LLM ID = 3 的记录:")
    results = query_prompts(llm_id=3, limit=10)
    print(f"   找到 {len(results)} 条记录")
    
    print("\n✓ 查询测试完成")


def test_stats():
    """Test statistics functionality."""
    print("\n=== 测试统计数据 ===")
    
    stats = get_prompt_stats()
    print(f"总调用次数: {stats['statistics']['total_calls']}")
    print(f"按 LLM ID 分布: {stats['statistics']['by_llm_id']}")
    print(f"按步骤分布: {stats['statistics']['by_step']}")
    print(f"按论文分布: {stats['statistics']['by_paper']}")
    
    print("\n✓ 统计测试完成")


def main():
    """Run all tests."""
    print("=" * 60)
    print("  Prompt 追踪系统测试")
    print("=" * 60)
    
    try:
        test_logging()
        test_query()
        test_stats()
        
        print("\n" + "=" * 60)
        print("  ✅ 所有测试通过！")
        print("=" * 60)
        print("\n💡 提示:")
        print("   - 访问 http://localhost:8000/static/prompts.html 查看前端界面")
        print("   - 使用 API: GET /api/prompts/query?limit=100")
        print("   - 查看详情: GET /api/prompts/detail/{manifest_file}")
        print("   - 查看统计: GET /api/prompts/stats")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
