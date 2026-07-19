"""
Multilingual Reasoning Model Fine-Tuning Script

This script demonstrates how to fine-tune OpenAI's gpt-oss-20b model using Hugging Face's TRL library,
enabling effective reasoning across multiple languages.

Based on the OpenAI Cookbook tutorial:
https://cookbook.openai.com/articles/gpt-oss/fine-tune-transfomers

Authors: Edward Beeching, Quentin Gallouédec, Lewis Tunstall
Modified: Adapted as a complete Python script

⚠️  Hardware Requirements (Important!):
- GPU: H100 (80GB VRAM) or higher
- Training time: Approximately 18 minutes on H100
- Uses Mxfp4Config quantization and LoRA for memory-efficient training

Features:
- Uses Mxfp4Config (4-bit floating point format optimized for OpenAI models)
- Memory-efficient fine-tuning with LoRA (including MoE expert layers)
- Supports multilingual reasoning (English, Spanish, French, German, Italian, etc.)
- Can mix languages (ask in one language, reason in another)
- All hyperparameters are identical to the OpenAI Cookbook tutorial
"""

import os
import argparse
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Mxfp4Config,
)
from peft import LoraConfig, PeftModel, get_peft_model
from trl import SFTTrainer, SFTConfig


# ============================================================================
#Part 1: Dataset Preparation
# ============================================================================

def load_and_prepare_dataset():
    """
    Load and prepare the multilingual reasoning dataset
    
    Uses the HuggingFaceH4/Multilingual-Thinking dataset, which contains:
    - Reasoning chains (chain-of-thought) in multiple languages
    - Supports English, Spanish, French, German, Italian, etc.
    
    Returns:
        Dataset: Formatted training dataset
    """
    print("=" * 80)
    print("Step 1: Load Dataset")
    print("=" * 80)
    
    # Load dataset from Hugging Face Hub
    dataset = load_dataset("HuggingFaceH4/Multilingual-Thinking")
    
    print(f"Dataset loaded!")
    print(f"Number of training samples: {len(dataset['train'])}")
    print(f"Dataset columns: {dataset['train'].column_names}")
    print(f"\nExample data:")
    print(dataset['train'][0])
    
    return dataset['train']


def format_chat_template(example, tokenizer):
    """
    Format conversation template
    
    Formats messages in the dataset into a conversation format understandable by the model
    
    Args:
        example: A sample from the dataset
        tokenizer: Tokenizer
        
    Returns:
        dict: Formatted sample
    """
    # Apply chat template
    example["text"] = tokenizer.apply_chat_template(
        example["messages"],
        tokenize=False,
    )
    return example


# ============================================================================
#Part 2: Model Preparation
# ============================================================================

def load_base_model(model_name="openai/gpt-oss-20b"):
    """
    Load base model and tokenizer
    
    Uses Mxfp4Config for quantization, a 4-bit floating point format optimized for OpenAI models.
    
    Args:
        model_name: Model name or path
        
    Returns:
        tuple: (model, tokenizer)
    """
    print("\n" + "=" * 80)
    print("Step 2: Load Base Model")
    print("=" * 80)
    
    # Load tokenizer
    print(f"Loading tokenizer: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # Set pad token (if not present)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Configure Mxfp4 quantization (optimized for OpenAI models)
    print("Quantizing with Mxfp4Config...")
    quantization_config = Mxfp4Config(dequantize=True)
    
    # Configure model loading parameters
    model_kwargs = {
        "attn_implementation": "eager",      # Attention implementation
        "torch_dtype": torch.bfloat16,       # Use bfloat16 for efficiency
        "quantization_config": quantization_config,  # Mxfp4 quantization configuration
        "use_cache": False,                   # Disable KV cache during training
        "device_map": "auto",                 # Automatically assign device
    }
    
    # Load model
    print(f"Loading model: {model_name}")
    print("This may take a few minutes...")
    model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    
    print(f"Model loaded!")
    print(f"Model parameters: {model.num_parameters() / 1e9:.2f}B")
    
    return model, tokenizer


def prepare_model_for_lora(model, lora_rank=8, lora_alpha=16):
    """
    Configure LoRA (Low-Rank Adaptation) for efficient fine-tuning
    
    LoRA trains only a small number of parameters, significantly reducing memory usage and training time.
    For the MoE (Mixture of Experts) architecture of openai/gpt-oss-20b, in addition to the attention layers,
    the MLP expert layers must be specifically targeted for training.
    
    Args:
        model: Base model
        lora_rank: LoRA rank (default 8, consistent with official tutorial)
        lora_alpha: LoRA scaling parameter (default 16)
        
    Returns:
        PeftModel: Model configured with LoRA
    """
    print("\n" + "=" * 80)
    print("Step 3: Configure LoRA")
    print("=" * 80)
    
    # LoRA configuration (consistent with OpenAI Cookbook)
    peft_config = LoraConfig(
        r=lora_rank,                     # LoRA rank
        lora_alpha=lora_alpha,           # LoRA scaling parameter
        target_modules="all-linear",     # Target all linear layers
        target_parameters=[              # Specific parameters for MoE expert layers
            "7.mlp.experts.gate_up_proj",
            "7.mlp.experts.down_proj",
            "15.mlp.experts.gate_up_proj",
            "15.mlp.experts.down_proj",
            "23.mlp.experts.gate_up_proj",
            "23.mlp.experts.down_proj",
        ],
    )
    
    print("LoRA configuration:")
    print(f"  - Rank: {lora_rank}")
    print(f"  - Alpha: {lora_alpha}")
    print(f"  - Target modules: {peft_config.target_modules}")
    print(f"  - MoE expert layer parameters: {len(peft_config.target_parameters)} ")
    
    # Apply LoRA
    model = get_peft_model(model, peft_config)
    
    # Print trainable parameter statistics
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_percent = 100 * trainable_params / total_params
    
    print(f"\nTrainable parameter statistics:")
    print(f"  - Trainable parameters: {trainable_params:,} ({trainable_percent:.2f}%)")
    print(f"  - Total parameters: {total_params:,}")
    
    return model


# ============================================================================
#Part 3: Training
# ============================================================================

def train_model(model, tokenizer, dataset, output_dir="./gpt-oss-20b-multilingual-reasoner", 
                batch_size=4, num_epochs=1, learning_rate=2e-4, max_seq_length=2048):
    """
    Train the model using SFTTrainer
    
    Args:
        model: Model configured with LoRA
        tokenizer: Tokenizer
        dataset: Training dataset
        output_dir: Output directory
        batch_size: Batch size (adjust based on GPU memory, default 4)
        num_epochs: Number of training epochs (default 1)
        learning_rate: Learning rate (default 2e-4)
        max_seq_length: Maximum sequence length
        
    Returns:
        SFTTrainer: Trained trainer object
    """
    print("\n" + "=" * 80)
    print("Step 4: Start training")
    print("=" * 80)
    
    # Training parameter configuration (exactly consistent with OpenAI Cookbook)
    training_args = SFTConfig(
        learning_rate=learning_rate,
        gradient_checkpointing=True,
        num_train_epochs=num_epochs,
        logging_steps=1,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        max_length=max_seq_length,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine_with_min_lr",
        lr_scheduler_kwargs={"min_lr_rate": 0.1},
        output_dir=output_dir,
        report_to="trackio",  # Set to "trackio" to enable experiment tracking
        push_to_hub=False,  # Set to True to automatically push to Hub
    )
    
    print("Training configuration:")
    print(f"  - Batch size: {batch_size}")
    print(f"  - Gradient accumulation steps: {training_args.gradient_accumulation_steps}")
    print(f"  - Effective batch size: {batch_size * training_args.gradient_accumulation_steps}")
    print(f"  - Number of epochs: {num_epochs}")
    print(f"  - Learning rate: {learning_rate}")
    print(f"  - Learning rate scheduler: {training_args.lr_scheduler_type}")
    print(f"  - Maximum sequence length: {max_seq_length}")
    print(f"  - Output directory: {output_dir}")
    
    #Initialize SFTTrainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    
    #Start training
    print("\nStarting training...")
    print("⚠️  Training on H100 GPU takes about 18 minutes")
    print("-" * 80)
    
    trainer.train()
    
    print("\n" + "=" * 80)
    print("Training complete!")
    print("=" * 80)
    
    return trainer


# ============================================================================
#  Part 4: Save and push model
# ============================================================================

def save_and_push_model(trainer, output_dir, push_to_hub=False, hub_model_id=None):
    """
    Save the model and optionally push to Hugging Face Hub
    
    Args:
        trainer: Trained trainer object
        output_dir: Output directory
        push_to_hub: Whether to push to Hub
        hub_model_id: Model ID on Hub
    """
    print("\n" + "=" * 80)
    print("Step 5: Save model")
    print("=" * 80)
    
    #  Save model locally
    print(f"Saving model to: {output_dir}")
    trainer.save_model(output_dir)
    print("Model saved!")
    
    #  Optional: Push to Hugging Face Hub
    if push_to_hub:
        if hub_model_id is None:
            raise ValueError("Need to provide hub_model_id to push to Hub")
        
        print(f"\nPushing model to Hugging Face Hub: {hub_model_id}")
        trainer.push_to_hub(
            dataset_name="HuggingFaceH4/Multilingual-Thinking",
        )
        print("Model successfully pushed to Hub!")


# ============================================================================
#  Part 5: Inference
# ============================================================================

def load_trained_model(base_model_name, peft_model_path):
    """
    Load the trained model for inference
    
    Args:
        base_model_name: Base model name
        peft_model_path: LoRA weight path
        
    Returns:
        tuple: (model, tokenizer)
    """
    print("\n" + "=" * 80)
    print("Load trained model for inference")
    print("=" * 80)
    
    # Load tokenizer
    print(f"Loading tokenizer: {base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    
    #  Load base model
    print(f"Loading base model: {base_model_name}")
    model_kwargs = {
        "attn_implementation": "eager",
        "torch_dtype": "auto",
        "use_cache": True,  #  Enable KV cache during inference
        "device_map": "auto",
    }
    base_model = AutoModelForCausalLM.from_pretrained(base_model_name, **model_kwargs)
    
    #  Load and merge LoRA weights
    print(f"Loading LoRA weights: {peft_model_path}")
    model = PeftModel.from_pretrained(base_model, peft_model_path)
    
    print("Merging LoRA weights with base model...")
    model = model.merge_and_unload()
    
    print("Model loaded!")
    
    return model, tokenizer


def generate_response(model, tokenizer, reasoning_language, user_prompt, 
                     max_new_tokens=512, temperature=0.6, format_output=True):
    """
    Generate multilingual inference response
    
    Args:
        model: Trained model
        tokenizer: Tokenizer
        reasoning_language: Language for reasoning
        user_prompt: User query
        max_new_tokens: Maximum number of new tokens to generate
        temperature: Sampling temperature (higher = more random)
        format_output: Whether to format output (with explicit markers)
        
    Returns:
        str: Generated complete response
    """
    #  Build messages
    system_prompt = f"reasoning language: {reasoning_language}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    # Apply chat template
    input_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(model.device)
    
    #  Generation config
    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": True,
        "temperature": temperature,
        "top_p": None,
        "top_k": None,
    }
    
    #  Generate response
    print(f"\nGenerating response...")
    print(f"Inference language: {reasoning_language}")
    print(f"User query: {user_prompt}")
    
    with torch.no_grad():
        output_ids = model.generate(input_ids, **gen_kwargs)
    
    # Decode output - preserve special markers for parsing
    response_with_tokens = tokenizer.batch_decode(output_ids, skip_special_tokens=False)[0]
    print("-" * 80)
    print(response_with_tokens)
    print("-" * 80)


def run_inference_examples(model, tokenizer):
    """
    Run multiple inference examples
    
    Args:
        model: trained model
        tokenizer: tokenizer
    """
    print("\n" + "=" * 80)
    print("Inference example")
    print("=" * 80)
    
    # Example 1: Spanish query, German inference
    print("\n[Example 1: Spanish query + German inference]")
    generate_response(
        model, tokenizer,
        reasoning_language="German",
        user_prompt="¿Cuál es el capital de Australia?",  # What is the capital of Australia?
        format_output=True,
    )
    
    # Example 2: English query, Chinese inference
    print("\n\n[Example 2: English query + Chinese inference]")
    generate_response(
        model, tokenizer,
        reasoning_language="Chinese",
        user_prompt="What is the national symbol of Canada?",
        format_output=True,
    )
    
    # Example 3: Chinese query, Chinese inference
    print("\n\n[Example 3: Chinese query + Chinese inference]")
    generate_response(
        model, tokenizer,
        reasoning_language="Chinese",
        user_prompt="Solve for the roots of x^2 - 2x + 1 = 0",
        format_output=True,
    )


# ============================================================================
# Main function
# ============================================================================

def main():
    """Main function: complete training pipeline"""
    
    parser = argparse.ArgumentParser(description="Multilingual inference model fine-tuning")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["train", "inference", "full"],
        default="full",
        help="Run mode: train (training only), inference (inference only), full (complete pipeline)"
    )
    parser.add_argument("--model_name", type=str, default="openai/gpt-oss-20b", help="Base model name")
    parser.add_argument("--output_dir", type=str, default="./gpt-oss-20b-multilingual-reasoner", help="Output directory")
    parser.add_argument("--batch_size", type=int, default=4, help="Training batch size (default 4, consistent with official tutorial)")
    parser.add_argument("--num_epochs", type=int, default=1, help="Number of training epochs (default 1, consistent with official tutorial)")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning rate (default 2e-4, consistent with official tutorial)")
    parser.add_argument("--max_seq_length", type=int, default=2048, help="Maximum sequence length")
    parser.add_argument("--lora_rank", type=int, default=8, help="LoRA rank (default 8, consistent with official tutorial)")
    parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA alpha")
    parser.add_argument("--push_to_hub", action="store_true", default=False, help="Push model to Hugging Face Hub")
    parser.add_argument("--hub_model_id", type=str, default=None, help="Hub model ID")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Multilingual inference model fine-tuning")
    print("=" * 80)
    print(f"Mode: {args.mode}")
    print(f"Base model: {args.model_name}")
    print(f"Output directory: {args.output_dir}")
    
    # Training mode
    if args.mode in ["train", "full"]:
        # 1. Load dataset
        dataset = load_and_prepare_dataset()
        
        # 2. Load base model (quantized with Mxfp4Config)
        model, tokenizer = load_base_model(args.model_name)
        
        # 3. Configure LoRA
        model = prepare_model_for_lora(model, args.lora_rank, args.lora_alpha)
        
        # 4. Train model
        trainer = train_model(
            model, 
            tokenizer, 
            dataset,
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            num_epochs=args.num_epochs,
            learning_rate=args.learning_rate,
            max_seq_length=args.max_seq_length,
        )
        
        # 5. Save model
        save_and_push_model(
            trainer, 
            args.output_dir,
            push_to_hub=args.push_to_hub,
            hub_model_id=args.hub_model_id,
        )
        
        print("\nTraining complete! It is recommended to restart the kernel to free GPU memory before inference.")
    
    # Inference mode
    if args.mode == "inference":
        if not os.path.exists(args.output_dir):
            print(f"Error: Model directory not found {args.output_dir}")
            print("Please run training first or specify the correct model path")
            return
        
        # Load trained model
        model, tokenizer = load_trained_model(args.model_name, args.output_dir)
        
        # Run inference example
        run_inference_examples(model, tokenizer)
    
    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()

