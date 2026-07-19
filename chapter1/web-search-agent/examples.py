"""
Advanced Example - Demonstrating Various Uses of Web Search Agent
"""

import asyncio
import json
from typing import List, Dict, Any
from agent import WebSearchAgent
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedWebSearchAgent(WebSearchAgent):
    """
    Advanced Web Search Agent - Extended Features
    """
    
    def batch_search(self, questions: List[str]) -> List[Dict[str, str]]:
        """
        Batch search for multiple questions
        
        Args:
            questions: List of questions
            
        Returns:
            List of answers
        """
        results = []
        for i, question in enumerate(questions, 1):
            logger.info(f"Processing question {i}/{len(questions)}: {question}")
            try:
                answer = self.search_and_answer(question)
                results.append({
                    "question": question,
                    "answer": answer,
                    "status": "success"
                })
            except Exception as e:
                results.append({
                    "question": question,
                    "answer": str(e),
                    "status": "error"
                })
            # Clear history to avoid context confusion
            self.clear_history()
        return results
    
    def search_with_context(self, question: str, context: str) -> str:
        """
        Search with context
        
        Args:
            question: User question
            context: Additional context information
            
        Returns:
            Answer
        """
        # Construct question with context
        contextualized_question = f"""
Background information:{context}

Based on the above background, please answer the following question:
{question}
"""
        return self.search_and_answer(contextualized_question)
    
    def comparative_search(self, items: List[str], aspect: str) -> str:
        """
        Comparison search - Search and compare multiple items
        
        Args:
            items: List of items to compare
            aspect: Aspect of comparison
            
        Returns:
            Comparison result
        """
        # Construct comparison question
        items_str = "、".join(items)
        question = f"Please search and compare {items_str} in terms of {aspect} differences and pros/cons"
        
        return self.search_and_answer(question)
    
    def fact_check(self, statement: str) -> Dict[str, Any]:
        """
        Fact check - Verify the truthfulness of a statement
        
        Args:
            statement: Statement to verify
            
        Returns:
            Verification result
        """
        question = f"""
Please verify the truthfulness of the following statement:
" {statement}"

Please provide:
1. Whether the statement is accurate (true/false/partially true)
2. Relevant facts and evidence
3. Sources of information
"""
        answer = self.search_and_answer(question)
        
        # Simple parse result
        is_true = "true" in answer[:100]
        return {
            "statement": statement,
            "is_true": is_true,
            "explanation": answer
        }


def example_basic_search():
    """Basic Search Example"""
    print("\n" + "="*60)
    print("📌 Example 1: Basic Search")
    print("="*60)
    
    agent = WebSearchAgent(Config.get_api_key())
    
    questions = [
        "What are the features of OpenAI's latest GPT model?",
        "How to learn machine learning? Recommend some resources",
    ]
    
    for q in questions:
        print(f"\nQuestion: {q}")
        print("-"*40)
        answer = agent.search_and_answer(q)
        print(f"Answer: {answer}")


def example_batch_search():
    """Batch Search Example"""
    print("\n" + "="*60)
    print("📌 Example 2: Batch Search")
    print("="*60)
    
    agent = AdvancedWebSearchAgent(Config.get_api_key())
    
    questions = [
        "What are the main differences between React and Vue?",
        "What type of projects is Python best suited for?",
        "How to start learning artificial intelligence?",
    ]
    
    results = agent.batch_search(questions)
    
    for result in results:
        print(f"\nQuestion: {result['question']}")
        print(f"Status: {result['status']}")
        print(f"Answer: {result['answer'][:200]}...")  # Only show first 200 characters


def example_contextual_search():
    """Search Example with Context"""
    print("\n" + "="*60)
    print("📌 Example 3: Search with Context")
    print("="*60)
    
    agent = AdvancedWebSearchAgent(Config.get_api_key())
    
    context = "I am a college student just starting to learn programming, mainly interested in Web development"
    question = "Which programming language should I learn first?"
    
    print(f"Context: {context}")
    print(f"Question: {question}")
    print("-"*40)
    
    answer = agent.search_with_context(question, context)
    print(f"Answer: {answer}")


def example_comparative_search():
    """Comparison Search Example"""
    print("\n" + "="*60)
    print("📌 Example 4: Comparison Search")
    print("="*60)
    
    agent = AdvancedWebSearchAgent(Config.get_api_key())
    
    # Compare different technology frameworks
    items = ["TensorFlow", "PyTorch", "JAX"]
    aspect = "Performance and ease of use"
    
    print(f"Comparison items: {', '.join(items)}")
    print(f"Comparison aspect: {aspect}")
    print("-"*40)
    
    result = agent.comparative_search(items, aspect)
    print(f"Comparison result:\n{result}")


def example_fact_check():
    """Fact-Checking Example"""
    print("\n" + "="*60)
    print("📌 Example 5: Fact-Checking")
    print("="*60)
    
    agent = AdvancedWebSearchAgent(Config.get_api_key())
    
    statements = [
        "Python is the most popular programming language in the world",
        "Quantum computers can already crack all modern encryption algorithms",
        "GPT-4 has 1.76 trillion parameters",
    ]
    
    for statement in statements:
        print(f"\nStatement: {statement}")
        result = agent.fact_check(statement)
        print(f"Truthfulness: {'✅ True' if result['is_true'] else '❌ False/Doubtful'}")
        print(f"Explanation: {result['explanation'][:200]}...")


def example_research_assistant():
    """Research Assistant Example - Deep Research on a Topic"""
    print("\n" + "="*60)
    print("📌 Example 6: Research Assistant - Deep Research")
    print("="*60)
    
    agent = AdvancedWebSearchAgent(Config.get_api_key())
    
    topic = "The development history of large language models"
    
    # Build a sequence of research questions
    research_questions = [
        f"What is{topic}? Please provide a detailed definition",
        f"{topic}What are the key milestones and important events?",
        f"{topic}What are the main challenges faced?",
        f"{topic}What are the future development trends?",
    ]
    
    print(f"Research topic: {topic}")
    print("="*60)
    
    research_report = []
    for i, q in enumerate(research_questions, 1):
        print(f"\nResearch question {i}: {q}")
        print("-"*40)
        answer = agent.search_and_answer(q)
        research_report.append({
            "section": i,
            "question": q,
            "findings": answer
        })
        print(f"Findings: {answer[:300]}...")
        agent.clear_history()  # Clear history to ensure each question is independent
    
    # Save research report
    with open("research_report.json", "w", encoding="utf-8") as f:
        json.dump(research_report, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Research report saved to research_report.json")


def main():
    """Run all examples"""
    
    if not Config.validate():
        print("Please set the KIMI_API_KEY environment variable first")
        return
    
    examples = [
        ("Basic search", example_basic_search),
        ("Batch search", example_batch_search),
        ("Contextual search", example_contextual_search),
        ("Comparative search", example_comparative_search),
        ("Fact check", example_fact_check),
        ("Research assistant", example_research_assistant),
    ]
    
    print("\n" + "="*60)
    print("🎯 Kimi Web Search Agent - Advanced Examples")
    print("="*60)
    print("\nSelect the example to run:")
    
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    print(f"{len(examples) + 1}. Run all examples")
    print("0. Exit")
    
    try:
        choice = input("\nPlease enter an option (0-7): ").strip()
        choice = int(choice)
        
        if choice == 0:
            print("Exit program")
            return
        elif 1 <= choice <= len(examples):
            examples[choice - 1][1]()
        elif choice == len(examples) + 1:
            for name, func in examples:
                try:
                    func()
                except Exception as e:
                    logger.error(f"Error running {name}: {str(e)}")
        else:
            print("Invalid option")
    except ValueError:
        print("Please enter a valid number")
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    except Exception as e:
        logger.error(f"Error running example: {str(e)}")


if __name__ == "__main__":
    main()
