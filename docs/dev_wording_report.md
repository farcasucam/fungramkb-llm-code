# Prompt robustness across wordings

| Model | Cond | W1 | W2 | W3 | max drop | consistency | n |
|---|---|---|---|---|---|---|---|
| llama3.1-8b-instruct-bf16 | G2 | 0.518 | 0.473 | 0.554 | +0.045 | 0.384 | 112 |
| llama3.1-8b-instruct-bf16 | N1P | 0.804 | 0.804 | 0.688 | +0.116 | 0.696 | 112 |
| olmo3-7b-instruct-bf16 | G2 | 0.661 | 0.607 | 0.598 | +0.062 | 0.527 | 112 |
| olmo3-7b-instruct-bf16 | N1P | 0.750 | 0.732 | 0.652 | +0.098 | 0.661 | 112 |
| qwen2.5-7b-instruct-bf16 | G2 | 0.634 | 0.571 | 0.652 | +0.062 | 0.571 | 112 |
| qwen2.5-7b-instruct-bf16 | N1P | 0.812 | 0.795 | 0.661 | +0.152 | 0.696 | 112 |

| Model | Contrast | wording | diff [95 % CI] |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | N1P − G2 | w1 | +28.6 [+16.1, +40.2] (n=112) |
| llama3.1-8b-instruct-bf16 | N1P − G2 | w2 | +33.0 [+20.0, +45.9] (n=112) |
| llama3.1-8b-instruct-bf16 | N1P − G2 | w3 | +13.4 [+0.0, +26.5] (n=112) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w1 | +8.9 [-4.4, +21.1] (n=112) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w2 | +12.5 [-1.8, +26.5] (n=112) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w3 | +5.4 [-7.2, +18.0] (n=112) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w1 | +17.9 [+6.2, +29.5] (n=112) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w2 | +22.3 [+8.8, +35.3] (n=112) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w3 | +0.9 [-11.7, +13.6] (n=112) |
