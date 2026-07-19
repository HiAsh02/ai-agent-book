# coding: utf-8
# Copyright (c) 2025 inclusionAI.
import asyncio

from dotenv import load_dotenv

from aworld.memory.main import MemoryFactory
from tests.memory.agent.self_evolving_agent import SuperAgent

async def _run_multi_session_examples() -> None:
    """
    Run examples across multiple sessions demonstrating a complete learning workflow.
    This example shows a deep learning process about Agent-RL (Reinforcement Learning Agents):
    1. Deep search and research on Agent-RL concepts and implementations
    2. Content revision and modification for specific aspects
    3. Text-to-speech conversion for learning materials
    4. Next-day review and reinforcement
    """
    # await init_dataset()

    super_agent = SuperAgent(id="super_agent", name="super_agent")
    user_id = "alice"

    # Day 1 - Session 1: Deep Search on Agent-RL
    session_id = "day1_morning_session"
    await super_agent.async_run(
        user_id=user_id,
        session_id=session_id,
        task_id="alice:day1_morning:task#1",
        user_input="I want to deeply understand reinforcement learning-based agents (Agent-RL). Please use DEEPSEARCH to help me research this topic, including: 1. Basic architecture (state space, action space, reward mechanism) 2. Common algorithms (DQN, PPO, SAC, etc.) 3. Environment interaction design 4. Implementation best practices"
    )
    await super_agent.async_run(
        user_id=user_id,
        session_id=session_id,
        task_id="alice:day1_morning:task#2",
        user_input="Based on the search results above, please generate a structured learning document (markdown), focusing on: 1. Theoretical framework 2. Code examples (implementing simple Agent-RL using Python) 3. Common issues and solutions"
    )

    # Day 1 - Session 2: Content Revision
    # session_id = "day1_afternoon_session"
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day1_afternoon:task#1",
    #     user_input="I think the 'Environment Interaction Design' section in the previously generated document needs supplementation. Specifically: 1. How to design appropriate reward functions 2. Representation methods for environment states 3. Design considerations for action space"
    # )
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day1_afternoon:task#2",
    #     user_input="Great! Now please help me convert the revised document into a more understandable form, especially explaining the mathematical concepts of reinforcement learning with common examples, preparing for voice content generation"
    # )

    # Day 1 - Session 3: TTS Generation
    # session_id = "day1_evening_session"
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day1_evening:task#1",
    #     user_input="Please convert the content into a voice file, requirements: 1. Moderate speaking speed 2. Clear explanation of key algorithms and mathematical concepts 3. Chapters organized in the order of 'theoretical foundation - algorithm implementation - practical application' 4. Generate subtitles"
    # )
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day1_evening:task#2",
    #     user_input="Please generate a knowledge graph for Agent-RL, including: 1. Core concept relationships 2. Algorithm classification 3. Application scenarios 4. Learning path suggestions"
    # )

    # Day 2 - Morning Review
    # session_id = "day2_morning_session"
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day2_morning:task#1",
    #     user_input="Good morning! Please help me review yesterday's learning content about Agent-RL. Specifically: 1. Review core concepts through the knowledge graph 2. Review the pros and cons of each algorithm 3. Check if key mathematical principles are understood"
    # )
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day2_morning:task#2",
    #     user_input="Based on the learned content, please recommend next steps for learning: 1. Advanced algorithms (e.g., MARL multi-agent reinforcement learning) 2. Practical project practice 3. Cutting-edge research directions"
    # )
    # await super_agent.async_run(
    #     user_id=user_id,
    #     session_id=session_id,
    #     task_id="alice:day2_morning:task#3",
    #     user_input="Please design a practical project for me to apply the learned Agent-RL knowledge. Requirements: 1. Moderate project difficulty 2. Include a complete code framework 3. Have clear evaluation metrics 4. Provide optimization suggestions"
    # )


# if __name__ == '__main__':
#     load_dotenv()
#
#     MemoryFactory.init()
#
#     # Run the multi-session example with concrete learning tasks
#     asyncio.run(_run_multi_session_examples())

