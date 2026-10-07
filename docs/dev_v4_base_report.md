# Prompt robustness across wordings

| Model | Cond | W1 | W2 | W3 | max drop | consistency | n |
|---|---|---|---|---|---|---|---|
| llama3.1-8b-instruct-bf16 | G2 | 0.596 | 0.471 | 0.548 | +0.125 | 0.471 | 104 |
| llama3.1-8b-instruct-bf16 | N1P | 0.846 | 0.817 | 0.663 | +0.183 | 0.654 | 104 |
| llama3.1-8b-instruct-bf16 | N1P2 | 0.894 | 0.817 | 0.683 | +0.212 | 0.740 | 104 |
| olmo3-7b-instruct-bf16 | G2 | 0.654 | 0.673 | 0.567 | +0.087 | 0.538 | 104 |
| olmo3-7b-instruct-bf16 | N1P | 0.750 | 0.788 | 0.644 | +0.106 | 0.644 | 104 |
| olmo3-7b-instruct-bf16 | N1P2 | 0.856 | 0.875 | 0.654 | +0.202 | 0.644 | 104 |
| qwen2.5-7b-instruct-bf16 | G2 | 0.548 | 0.596 | 0.567 | +0.000 | 0.548 | 104 |
| qwen2.5-7b-instruct-bf16 | N1P | 0.846 | 0.856 | 0.625 | +0.221 | 0.606 | 104 |
| qwen2.5-7b-instruct-bf16 | N1P2 | 0.894 | 0.817 | 0.673 | +0.221 | 0.635 | 104 |

| Model | Contrast | wording | diff [95 % CI] |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | N1P − G2 | w1 | +25.0 [+12.3, +37.5] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P − G2 | w2 | +34.6 [+20.8, +47.6] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P − G2 | w3 | +11.5 [-2.9, +26.5] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w1 | +29.8 [+18.1, +42.2] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w2 | +34.6 [+21.2, +48.0] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w3 | +13.5 [-0.9, +28.7] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − N1P | w1 | +4.8 [-1.9, +12.0] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − N1P | w2 | +0.0 [-6.6, +7.5] (n=104) |
| llama3.1-8b-instruct-bf16 | N1P2 − N1P | w3 | +1.9 [-6.7, +10.6] (n=104) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w1 | +9.6 [-4.0, +22.3] (n=104) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w2 | +11.5 [-1.9, +24.8] (n=104) |
| olmo3-7b-instruct-bf16 | N1P − G2 | w3 | +7.7 [-5.9, +21.0] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w1 | +20.2 [+8.7, +31.7] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w2 | +20.2 [+8.7, +31.7] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w3 | +8.7 [-4.8, +21.9] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − N1P | w1 | +10.6 [+4.8, +17.6] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − N1P | w2 | +8.7 [+2.0, +15.4] (n=104) |
| olmo3-7b-instruct-bf16 | N1P2 − N1P | w3 | +1.0 [-7.5, +8.8] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w1 | +29.8 [+17.9, +42.6] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w2 | +26.0 [+13.9, +38.3] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P − G2 | w3 | +5.8 [-7.8, +20.4] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w1 | +34.6 [+23.8, +46.2] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w2 | +22.1 [+8.7, +35.6] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w3 | +10.6 [-3.9, +27.2] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − N1P | w1 | +4.8 [-1.0, +11.1] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − N1P | w2 | -3.8 [-9.7, +1.9] (n=104) |
| qwen2.5-7b-instruct-bf16 | N1P2 − N1P | w3 | +4.8 [-2.9, +13.2] (n=104) |

W3 by subject change (the paraphrase's grammatical subject is not the queried concept)

| Model | Cond | same subject: W1 / W3 (n) | subject changed: W1 / W3 (n) |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | G2 | 0.593 / 0.549 (91) | 0.615 / 0.538 (13) |
| llama3.1-8b-instruct-bf16 | N1P | 0.824 / 0.692 (91) | 1.000 / 0.462 (13) |
| llama3.1-8b-instruct-bf16 | N1P2 | 0.890 / 0.714 (91) | 0.923 / 0.462 (13) |
| olmo3-7b-instruct-bf16 | G2 | 0.659 / 0.593 (91) | 0.615 / 0.385 (13) |
| olmo3-7b-instruct-bf16 | N1P | 0.725 / 0.648 (91) | 0.923 / 0.615 (13) |
| olmo3-7b-instruct-bf16 | N1P2 | 0.835 / 0.637 (91) | 1.000 / 0.769 (13) |
| qwen2.5-7b-instruct-bf16 | G2 | 0.549 / 0.571 (91) | 0.538 / 0.538 (13) |
| qwen2.5-7b-instruct-bf16 | N1P | 0.835 / 0.648 (91) | 0.923 / 0.462 (13) |
| qwen2.5-7b-instruct-bf16 | N1P2 | 0.879 / 0.703 (91) | 1.000 / 0.462 (13) |
