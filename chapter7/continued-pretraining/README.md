# Continued Pretraining: Teaching a Model a New Language (Korean Mistral)

> This directory corresponds to Chapter 7, **Experiment 7-5 ★★: Continued Pretraining for Learning a New Language** of *Deep Understanding of AI Agents*.

## Project Overview

Using **Mistral 7B v0.3** as the base model (primarily pretrained on English, with virtually no understanding of Korean), we inject Korean language capability through **continued pretraining on Korean Wikipedia**, followed by **SFT on Korean instruction data**. The final model can both understand Korean and follow instructions in Korean.

The core idea this experiment aims to demonstrate: **To make a model memorize a large amount of new domain knowledge (here, a new language), rely on continued pretraining, not SFT.** The model already possesses general language modeling ability from the pretraining phase; continued pretraining merely adapts it to a new data distribution, at a cost far lower than training from scratch.

The entire process consists of two stages:

1. **Continued Pretraining**: Unsupervised "predict the next token" training on Korean Wikipedia, allowing the model to learn Korean vocabulary and syntax.
2. **Instruction Fine-Tuning (SFT)**: Training on Korean Alpaca instruction data to teach the model to "follow instructions in Korean."

A key engineering challenge is **mitigating Catastrophic Forgetting**: learning a new language should not cause the model to forget its original English ability. The common approach discussed in the book uses mixed data (approximately 80% target language + 20% original language) to balance this; this implementation adopts a parameter-efficient scheme using **LoRA + training `embed_tokens`/`lm_head`** — only updating the adapters and word embeddings while keeping the base weights unchanged, thereby preserving English as much as possible while injecting Korean. Evaluation results (see below) show that English ability is largely retained.

## Directory Structure

```
continued-pretraining/
├── README.md                 # This document
├── continued-pretrain.py     # Main training script: continued pretraining + SFT, produces two LoRA models
├── evaluate_model.py         # Single model evaluation: generates samples on Korean/English tasks
├── compare_models.py         # Three-stage comparison: base → continued pretraining → instruction fine-tuning side-by-side generation
├── model_eval_results.md     # Full evaluation output and conclusions from actual run (RTX 4090)
├── README_EVALUATION.md      # Detailed usage instructions for evaluation scripts
└── requirements.txt          # Dependency list
```

Running the training script produces two local directories (saving only LoRA adapters, not the full model):

- `lora_model_pretrained/`: Model after continued pretraining, before SFT
- `lora_model/`: Model after final instruction fine-tuning

## System Requirements & Dependencies

- **GPU**: Requires a CUDA-capable NVIDIA GPU. By default, Mistral-7B is loaded in 4-bit quantization, allowing training on consumer-grade GPUs with approximately 24GB VRAM (e.g., RTX 4090). The results in `model_eval_results.md` were produced on an RTX 4090.
- **Framework**: [Unsloth](https://github.com/unslothai/unsloth) (efficient LoRA training), PyTorch, Transformers, Datasets, bitsandbytes.
- **Optional**: wandb (experiment tracking; script defaults to `report_to="wandb"`).

```bash
pip install -r requirements.txt
```

> Note: Unsloth depends on a GPU with a compatible CUDA/PyTorch version and cannot be used for training or inference in a pure CPU environment. The `--help` for each script uses lazy imports, so parameter descriptions can be viewed on machines without a GPU.

## Quick Start

### 1. Training (Continued Pretraining + SFT)

Run both stages with default hyperparameters in one command (using a 5% subset of Korean Wikipedia for continued pretraining, followed by SFT on Korean Alpaca):

```bash
python continued-pretrain.py
```

The script will sequentially: load the base model → print a baseline test → perform continued pretraining on Korean Wikipedia → save `lora_model_pretrained/` → perform SFT on Korean instructions → save `lora_model/`.

Common parameters (defaults match the script's original hardcoded values; changes will deviate from the original experiment):

```bash
python continued-pretrain.py \
    --base_model unsloth/mistral-7b-v0.3 \
    --wiki_config 20231101.ko \
    --wiki_train_size 0.05 \
    --alpaca_dataset FreedomIntelligence/alpaca-gpt4-korean \
    --lora_rank 128 \
    --max_seq_len 2048 \
    --pretrain_epochs 1 \
    --sft_epochs 2 \
    --pretrained_save_dir lora_model_pretrained \
    --final_save_dir lora_model
```

- For a quick smoke test, use `--pretrain_max_steps 20 --sft_max_steps 20` to run only a few steps.
- To switch to a different language: replace `--wiki_config` with the corresponding Wikipedia snapshot (e.g., `20231101.ja` for Japanese) and `--alpaca_dataset` with the corresponding instruction dataset.
- See `python continued-pretrain.py --help` for the full list of parameters.

### 2. Evaluating a Single Model

```bash
# Evaluate the final fine-tuned model (default loads lora_model/)
python evaluate_model.py

# Evaluate the model after continued pretraining, before SFT
python evaluate_model.py --pretrained

# Generate longer outputs using sampling
python evaluate_model.py --max_new_tokens 300 --use_sampling --temperature 0.7
```

See [`README_EVALUATION.md`](./README_EVALUATION.md) for more usage details.

### 3. Three-Stage Side-by-Side Comparison

Load the **base model / continued pretraining model / instruction fine-tuning model** simultaneously and generate side-by-side outputs on the same set of Korean and English prompts, visually demonstrating the improvement in Korean ability and the retention of English ability:

```bash
python compare_models.py
```

```bash
# Specify model directories and generation parameters
python compare_models.py \
    --pretrained_path lora_model_pretrained \
    --finetuned_path lora_model \
    --max_new_tokens 150 \
    --temperature 0.3
```

## Experimental Results

The full output, item-by-item comparisons, and conclusions from the actual run can be found in [`model_eval_results.md`](./model_eval_results.md) (produced on an RTX 4090; please refer to the actual results in that file, as this document will not repeat the specific values). The main conclusions can be summarized as:

- **Methodology is valid**: Continued pretraining + SFT can indeed inject new language ability into a model. Korean improved from "basically unusable" to "fluent and able to follow instructions," while English ability was largely retained (no significant catastrophic forgetting).
- **Data quality is the bottleneck**: Using only 5% of Wikipedia corpus, general language ability improved significantly, but specific cultural knowledge (e.g., kimchi) still often produced errors — indicating that for specific knowledge domains, **data coverage and quality are more critical than the training method itself**.

## References

- Unsloth documentation: https://docs.unsloth.ai
- Base model: [unsloth/mistral-7b-v0.3](https://huggingface.co/unsloth/mistral-7b-v0.3)
- Continued pretraining corpus: [wikimedia/wikipedia](https://huggingface.co/datasets/wikimedia/wikipedia) (`20231101.ko`)
- Instruction fine-tuning corpus: [FreedomIntelligence/alpaca-gpt4-korean](https://huggingface.co/datasets/FreedomIntelligence/alpaca-gpt4-korean)
