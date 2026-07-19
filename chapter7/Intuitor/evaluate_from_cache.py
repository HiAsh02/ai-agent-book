#!/usr/bin/env python3
"""
Extract answers from lighteval cached parquet files and compute GSM8K accuracy
Supports both \\boxed{} and #### answer formats
"""

import re
import pandas as pd
import argparse
from pathlib import Path
from typing import Optional


def extract_answer_from_boxed(text: str) -> Optional[str]:
    """Extract answer from \\boxed{} format (also supports \\(\\boxed{}\\) form)"""
    if not text:
        return None
    
    # If it's bytes, convert to string
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    
    # Ensure it's a string
    text = str(text)
    
    # Match \\boxed{number}, this pattern matches both \boxed{} and \(\boxed{}\)
    match = re.search(r'\\boxed\{([^}]+)\}', text)
    if match:
        return match.group(1).strip()
    
    return None


def extract_answer_from_gsm8k_format(text: str) -> Optional[str]:
    """Extract answer from #### number format"""
    if not text:
        return None
    
    # If it's bytes, convert to string
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    
    # Ensure it's a string
    text = str(text)
    
    if "####" in text:
        parts = text.split("####")
        if len(parts) > 1:
            return parts[1].strip()
    
    return None


def normalize_number(text: str) -> Optional[str]:
    """Normalize number format: remove commas, spaces, LaTeX symbols, etc."""
    if not text:
        return None
    
    # If it's bytes, convert to string
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    
    # Ensure it's a string
    text = str(text)
    
    # Remove LaTeX symbols
    text = text.replace("\\,", "")
    text = text.replace("\\text", "")
    text = text.replace("{", "").replace("}", "")
    
    # Remove commas and spaces
    text = text.replace(",", "").replace(" ", "")
    
    # Extract number (including decimals and negatives)
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        num_str = match.group(0)
        # Convert to float then back to string to normalize format
        try:
            num = float(num_str)
            # If it's an integer, return integer format
            if num.is_integer():
                return str(int(num))
            else:
                return str(num)
        except ValueError:
            return None
    
    return None


def extract_and_normalize_answer(text: str) -> Optional[str]:
    """Extract and normalize answer from model output"""
    if not text:
        return None
    
    # If it's bytes, convert to string
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='ignore')
    
    # Ensure it's a string
    text = str(text)
    
    # First try to extract boxed format
    answer = extract_answer_from_boxed(text)
    
    # If not found, try GSM8K format
    if not answer:
        answer = extract_answer_from_gsm8k_format(text)
    
    # If still not found, try to extract number from the last sentence
    if not answer:
        # Take last 200 characters to avoid extracting intermediate numbers
        last_part = text[-200:] if len(text) > 200 else text
        answer = last_part
    
    # Normalize number format
    return normalize_number(answer)


def load_gsm8k_answers(split: str = "test") -> dict:
    """Load gold answers from GSM8K dataset
    
    Returns a dictionary with keys as original indices in the dataset (0-1318) and values as normalized answers
    """
    try:
        from datasets import load_dataset
        dataset = load_dataset("gsm8k", "main", split=split)
        
        answers = {}
        # Note: indices here are sequential indices in the dataset, not sample_id
        for idx in range(len(dataset)):
            item = dataset[idx]
            # GSM8K answer format: calculation process\n#### answer
            gold_answer = item["answer"]
            # Extract number after ####
            normalized = extract_answer_from_gsm8k_format(gold_answer)
            if normalized:
                normalized = normalize_number(normalized)
            answers[idx] = normalized
        
        print(f"✅ Loaded {len(answers)} gold answers")
        return answers
    except ImportError:
        print("❌ Error: datasets library required")
        print("Run: pip install datasets")
        return {}
    except Exception as e:
        print(f"❌ Error loading gold answers: {e}")
        return {}


def evaluate_from_parquet(parquet_path: str, verbose: bool = False):
    """Evaluate from parquet file"""
    print(f"📂 Reading predictions: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    
    print(f"📊 Total samples: {len(df)}")
    
    #  Load gold standard answers
    print("📥 Loading GSM8K gold standard answers...")
    gold_answers = load_gsm8k_answers()
    
    if not gold_answers:
        print("❌ Unable to load gold standard answers, exiting")
        return
    
    #  Evaluation
    correct = 0
    total = 0
    errors = []
    
    #  Debug: show first few sample_ids
    if verbose:
        print(f"\nFirst 5 sample_ids: {df['sample_id'].head().tolist()}")
        print(f"Gold standard answer key range: {min(gold_answers.keys()) if gold_answers else 'N/A'} - {max(gold_answers.keys()) if gold_answers else 'N/A'}")
    
    for idx, row in df.iterrows():
        sample_id = row['sample_id']
        sample_data = row['sample']
        
        #  Convert sample_id to integer (if it is a string)
        if isinstance(sample_id, str):
            try:
                sample_id = int(sample_id)
            except ValueError:
                if verbose:
                    print(f"⚠️  Sample {sample_id}: cannot convert to integer")
                continue
        
        #  Extract model output
        model_output = sample_data.get('text', [''])[0] if isinstance(sample_data.get('text'), list) else sample_data.get('text', '')
        
        #  Ensure model_output is a string
        if isinstance(model_output, bytes):
            model_output = model_output.decode('utf-8', errors='ignore')
        model_output = str(model_output) if model_output else ''
        
        #  Extract and normalize answer
        pred_answer = extract_and_normalize_answer(model_output)
        gold_answer = gold_answers.get(sample_id)
        
        if gold_answer is None:
            if verbose and idx < 5:
                print(f"⚠️  Sample {sample_id}: gold standard answer not found")
            continue
        
        total += 1
        is_correct = pred_answer == gold_answer
        
        if is_correct:
            correct += 1
        else:
            errors.append({
                'sample_id': sample_id,
                'predicted': pred_answer,
                'gold': gold_answer,
                'output': model_output[:200] + "..." if len(model_output) > 200 else model_output
            })
        
        if verbose and idx < 5:
            print(f"\nSample {sample_id}:")
            print(f"  Prediction: {pred_answer}")
            print(f"  Gold: {gold_answer}")
            print(f"  Correct: {'✅' if is_correct else '❌'}")
    
    #  Calculate accuracy
    accuracy = correct / total * 100 if total > 0 else 0
    
    print("\n" + "="*80)
    print("📈 Evaluation results")
    print("="*80)
    print(f"Total samples: {total}")
    print(f"Correct count: {correct}")
    print(f"Incorrect count: {total - correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    print("="*80)
    
    #  Show some incorrect samples
    if errors and verbose:
        print("\n❌ First 10 incorrect samples:")
        for i, error in enumerate(errors[:10], 1):
            print(f"\n{i}. Sample {error['sample_id']}:")
            print(f"   Prediction: {error['predicted']}")
            print(f"   Gold: {error['gold']}")
            print(f"   Output: {error['output']}")
    
    return {
        'total': total,
        'correct': correct,
        'accuracy': accuracy,
        'errors': errors
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate GSM8K results from lighteval cache')
    parser.add_argument('parquet_file', type=str, help='Parquet file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show details and error samples')
    parser.add_argument('-o', '--output', type=str, help='Save results to JSON file')
    
    args = parser.parse_args()
    
    if not Path(args.parquet_file).exists():
        print(f"❌ Error: file does not exist: {args.parquet_file}")
        return
    
    results = evaluate_from_parquet(args.parquet_file, verbose=args.verbose)
    
    if args.output and results:
        import json
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved to: {args.output}")


if __name__ == "__main__":
    main()

