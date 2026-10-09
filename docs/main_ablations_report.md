# Main study: ablations S3 and S4

## S3: lexicon-expanded KB minus base KB

| Model | Cond | Wording | base | lex | diff [95 % CI] | p | n |
|---|---|---|---|---|---|---|---|
| llama3.1-8b-instruct-bf16 | G2 | w1 | 0.552 | 0.555 | +0.3 [-1.1, +1.8] | 0.805 | 1484 |
| llama3.1-8b-instruct-bf16 | G2 | w2 | 0.575 | 0.571 | -0.5 [-1.8, +0.9] | 0.655 | 1484 |
| llama3.1-8b-instruct-bf16 | G2 | w3 | 0.566 | 0.558 | -0.7 [-2.7, +1.3] | 0.449 | 1103 |
| llama3.1-8b-instruct-bf16 | N1P2 | w1 | 0.855 | 0.861 | +0.5 [-0.3, +1.3] | 0.180 | 1484 |
| llama3.1-8b-instruct-bf16 | N1P2 | w2 | 0.849 | 0.849 | +0.0 [-0.8, +0.8] | 0.706 | 1484 |
| llama3.1-8b-instruct-bf16 | N1P2 | w3 | 0.707 | 0.662 | -4.5 [-6.1, -3.1] | 0.000 | 1103 |
| olmo3-7b-instruct-bf16 | G2 | w1 | 0.682 | 0.694 | +1.2 [+0.0, +2.4] | 0.018 | 1484 |
| olmo3-7b-instruct-bf16 | G2 | w2 | 0.701 | 0.710 | +0.9 [-0.5, +2.3] | 0.141 | 1484 |
| olmo3-7b-instruct-bf16 | G2 | w3 | 0.623 | 0.635 | +1.2 [-1.0, +3.3] | 0.231 | 1103 |
| olmo3-7b-instruct-bf16 | N1P2 | w1 | 0.801 | 0.799 | -0.1 [-0.9, +0.6] | 0.527 | 1484 |
| olmo3-7b-instruct-bf16 | N1P2 | w2 | 0.822 | 0.813 | -0.9 [-1.9, -0.1] | 0.039 | 1484 |
| olmo3-7b-instruct-bf16 | N1P2 | w3 | 0.592 | 0.599 | +0.7 [-0.9, +2.4] | 0.393 | 1103 |
| qwen2.5-7b-instruct-bf16 | G2 | w1 | 0.714 | 0.706 | -0.8 [-1.9, +0.3] | 0.191 | 1484 |
| qwen2.5-7b-instruct-bf16 | G2 | w2 | 0.703 | 0.705 | +0.2 [-1.1, +1.5] | 0.466 | 1484 |
| qwen2.5-7b-instruct-bf16 | G2 | w3 | 0.682 | 0.678 | -0.4 [-2.3, +1.6] | 0.865 | 1103 |
| qwen2.5-7b-instruct-bf16 | N1P2 | w1 | 0.868 | 0.867 | -0.1 [-0.6, +0.3] | 0.467 | 1484 |
| qwen2.5-7b-instruct-bf16 | N1P2 | w2 | 0.849 | 0.838 | -1.1 [-2.0, -0.3] | 0.039 | 1484 |
| qwen2.5-7b-instruct-bf16 | N1P2 | w3 | 0.688 | 0.677 | -1.1 [-2.3, +0.2] | 0.121 | 1103 |

## S4: G2 with one component removed minus full G2

| Model | Ablation | Items | full G2 | ablated | diff [95 % CI] | p | n |
|---|---|---|---|---|---|---|---|
| qwen2.5-7b-instruct-bf16 | +postulates | all | 0.714 | 0.726 | +1.1 [-0.4, +2.7] | 0.346 | 1484 |
| qwen2.5-7b-instruct-bf16 | +postulates | exceptions | 0.823 | 0.853 | +3.0 [-0.9, +6.8] | 0.275 | 231 |
| qwen2.5-7b-instruct-bf16 | +postulates | deep_real | 0.899 | 0.889 | -1.0 [-2.9, +1.0] | 0.320 | 208 |
| qwen2.5-7b-instruct-bf16 | +postulates | novel | 0.725 | 0.742 | +1.6 [-2.4, +5.8] | 0.725 | 244 |
| qwen2.5-7b-instruct-bf16 | -fillers | all | 0.714 | 0.715 | +0.1 [-1.8, +2.0] | 0.951 | 1484 |
| qwen2.5-7b-instruct-bf16 | -fillers | exceptions | 0.823 | 0.844 | +2.2 [-3.1, +7.8] | 0.524 | 231 |
| qwen2.5-7b-instruct-bf16 | -fillers | deep_real | 0.899 | 0.861 | -3.8 [-7.7, -0.5] | 0.090 | 208 |
| qwen2.5-7b-instruct-bf16 | -fillers | novel | 0.725 | 0.734 | +0.8 [-2.9, +4.8] | 0.685 | 244 |
| qwen2.5-7b-instruct-bf16 | -hedges | all | 0.714 | 0.706 | -0.9 [-3.1, +1.3] | 0.418 | 1484 |
| qwen2.5-7b-instruct-bf16 | -hedges | exceptions | 0.823 | 0.749 | -7.4 [-14.3, +0.0] | 0.100 | 231 |
| qwen2.5-7b-instruct-bf16 | -hedges | deep_real | 0.899 | 0.870 | -2.9 [-6.4, +0.9] | 0.227 | 208 |
| qwen2.5-7b-instruct-bf16 | -hedges | novel | 0.725 | 0.754 | +2.9 [-1.7, +7.8] | 0.287 | 244 |
