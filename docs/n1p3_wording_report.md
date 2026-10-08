# Prompt robustness across wordings

| Model | Cond | W1 | W2 | W3 | max drop | consistency | n |
|---|---|---|---|---|---|---|---|
| llama3.1-8b-instruct-bf16 | B1 | 0.403 | 0.403 | 0.444 | +0.000 | 0.493 | 1103 |
| llama3.1-8b-instruct-bf16 | G2 | 0.555 | 0.578 | 0.566 | +0.000 | 0.508 | 1103 |
| llama3.1-8b-instruct-bf16 | G3 | 0.429 | 0.457 | 0.452 | +0.000 | 0.456 | 1103 |
| llama3.1-8b-instruct-bf16 | N1P2 | 0.874 | 0.850 | 0.707 | +0.167 | 0.711 | 1103 |
| llama3.1-8b-instruct-bf16 | N1P3 | 0.902 | 0.893 | 0.800 | +0.102 | 0.822 | 1103 |
| olmo3-7b-instruct-bf16 | B1 | 0.451 | 0.471 | 0.456 | +0.000 | 0.407 | 1103 |
| olmo3-7b-instruct-bf16 | G2 | 0.684 | 0.696 | 0.623 | +0.062 | 0.539 | 1103 |
| olmo3-7b-instruct-bf16 | G3 | 0.454 | 0.455 | 0.462 | +0.000 | 0.388 | 1103 |
| olmo3-7b-instruct-bf16 | N1P2 | 0.814 | 0.832 | 0.592 | +0.222 | 0.662 | 1103 |
| olmo3-7b-instruct-bf16 | N1P3 | 0.850 | 0.850 | 0.709 | +0.141 | 0.754 | 1103 |
| qwen2.5-7b-instruct-bf16 | B1 | 0.465 | 0.472 | 0.451 | +0.014 | 0.462 | 1103 |
| qwen2.5-7b-instruct-bf16 | G2 | 0.707 | 0.695 | 0.682 | +0.025 | 0.662 | 1103 |
| qwen2.5-7b-instruct-bf16 | G3 | 0.456 | 0.464 | 0.470 | +0.000 | 0.510 | 1103 |
| qwen2.5-7b-instruct-bf16 | N1P2 | 0.882 | 0.859 | 0.688 | +0.194 | 0.722 | 1103 |
| qwen2.5-7b-instruct-bf16 | N1P3 | 0.889 | 0.894 | 0.788 | +0.102 | 0.825 | 1103 |

| Model | Contrast | wording | diff [95 % CI] |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | G2 − B1 | w1 | +15.2 [+11.0, +19.1] (n=1103) |
| llama3.1-8b-instruct-bf16 | G2 − B1 | w2 | +17.6 [+14.1, +21.2] (n=1103) |
| llama3.1-8b-instruct-bf16 | G2 − B1 | w3 | +12.1 [+8.9, +15.5] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w1 | +31.9 [+27.7, +36.3] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w2 | +27.2 [+22.7, +31.6] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P2 − G2 | w3 | +14.1 [+8.8, +19.8] (n=1103) |
| llama3.1-8b-instruct-bf16 | G2 − G3 | w1 | +12.6 [+8.9, +16.2] (n=1103) |
| llama3.1-8b-instruct-bf16 | G2 − G3 | w2 | +12.1 [+9.0, +15.7] (n=1103) |
| llama3.1-8b-instruct-bf16 | G2 − G3 | w3 | +11.3 [+8.1, +14.7] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − N1P2 | w1 | +2.8 [+1.9, +3.8] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − N1P2 | w2 | +4.3 [+3.2, +5.5] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − N1P2 | w3 | +9.2 [+7.1, +11.5] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − G2 | w1 | +34.7 [+30.8, +38.7] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − G2 | w2 | +31.5 [+27.3, +35.6] (n=1103) |
| llama3.1-8b-instruct-bf16 | N1P3 − G2 | w3 | +23.4 [+18.7, +28.3] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − B1 | w1 | +23.4 [+19.2, +27.7] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − B1 | w2 | +22.5 [+18.2, +26.8] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − B1 | w3 | +16.7 [+12.8, +20.6] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w1 | +13.0 [+8.9, +17.1] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w2 | +13.6 [+9.5, +17.7] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P2 − G2 | w3 | -3.1 [-8.2, +1.8] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − G3 | w1 | +23.0 [+18.9, +26.8] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − G3 | w2 | +24.1 [+20.2, +28.1] (n=1103) |
| olmo3-7b-instruct-bf16 | G2 − G3 | w3 | +16.0 [+12.3, +19.8] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − N1P2 | w1 | +3.6 [+2.6, +4.7] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − N1P2 | w2 | +1.7 [+1.0, +2.5] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − N1P2 | w3 | +11.7 [+9.3, +14.2] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − G2 | w1 | +16.6 [+12.8, +20.5] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − G2 | w2 | +15.3 [+11.3, +19.3] (n=1103) |
| olmo3-7b-instruct-bf16 | N1P3 − G2 | w3 | +8.6 [+4.1, +13.2] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − B1 | w1 | +24.2 [+19.8, +28.4] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − B1 | w2 | +22.3 [+17.7, +26.8] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − B1 | w3 | +23.0 [+19.4, +26.9] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w1 | +17.5 [+13.4, +21.8] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w2 | +16.3 [+11.9, +20.8] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P2 − G2 | w3 | +0.6 [-4.7, +5.9] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − G3 | w1 | +25.1 [+21.5, +28.9] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − G3 | w2 | +23.1 [+19.3, +27.0] (n=1103) |
| qwen2.5-7b-instruct-bf16 | G2 − G3 | w3 | +21.2 [+17.7, +24.7] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − N1P2 | w1 | +0.7 [+0.2, +1.4] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − N1P2 | w2 | +3.5 [+2.5, +4.7] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − N1P2 | w3 | +10.0 [+7.6, +12.4] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − G2 | w1 | +18.2 [+14.2, +22.4] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − G2 | w2 | +19.9 [+15.7, +24.3] (n=1103) |
| qwen2.5-7b-instruct-bf16 | N1P3 − G2 | w3 | +10.6 [+5.8, +15.2] (n=1103) |

W3 by subject change (the paraphrase's grammatical subject is not the queried concept)

| Model | Cond | same subject: W1 / W3 (n) | subject changed: W1 / W3 (n) |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | B1 | 0.405 / 0.446 (964) | 0.388 / 0.432 (139) |
| llama3.1-8b-instruct-bf16 | G2 | 0.560 / 0.563 (964) | 0.518 / 0.583 (139) |
| llama3.1-8b-instruct-bf16 | G3 | 0.437 / 0.454 (964) | 0.374 / 0.439 (139) |
| llama3.1-8b-instruct-bf16 | N1P2 | 0.868 / 0.741 (964) | 0.914 / 0.475 (139) |
| llama3.1-8b-instruct-bf16 | N1P3 | 0.895 / 0.806 (964) | 0.950 / 0.755 (139) |
| olmo3-7b-instruct-bf16 | B1 | 0.455 / 0.469 (964) | 0.417 / 0.367 (139) |
| olmo3-7b-instruct-bf16 | G2 | 0.693 / 0.626 (964) | 0.626 / 0.604 (139) |
| olmo3-7b-instruct-bf16 | G3 | 0.460 / 0.469 (964) | 0.417 / 0.417 (139) |
| olmo3-7b-instruct-bf16 | N1P2 | 0.810 / 0.603 (964) | 0.842 / 0.518 (139) |
| olmo3-7b-instruct-bf16 | N1P3 | 0.851 / 0.718 (964) | 0.849 / 0.647 (139) |
| qwen2.5-7b-instruct-bf16 | B1 | 0.471 / 0.460 (964) | 0.424 / 0.396 (139) |
| qwen2.5-7b-instruct-bf16 | G2 | 0.709 / 0.686 (964) | 0.698 / 0.655 (139) |
| qwen2.5-7b-instruct-bf16 | G3 | 0.460 / 0.484 (964) | 0.432 / 0.367 (139) |
| qwen2.5-7b-instruct-bf16 | N1P2 | 0.886 / 0.721 (964) | 0.856 / 0.460 (139) |
| qwen2.5-7b-instruct-bf16 | N1P3 | 0.891 / 0.791 (964) | 0.878 / 0.763 (139) |
