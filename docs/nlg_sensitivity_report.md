# Sensitivity to NLG errors (faithfulness audit v2)

Analysis set: 1484 items, 792 twin clusters. Items flagged: refugee 12, spurious_many 79, do_light 73, something 16.

## Set 'agreed': 83 clusters dropped, 1327 items kept

| model | test | full | kept |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | H1 G2>B1 | +14.8 (p=7.56e-15) | +14.9 (p=4.16e-14) |
| llama3.1-8b-instruct-bf16 | H2 G2>G1 | +8.9 (p=1.53e-07) | +8.5 (p=2.04e-06) |
| llama3.1-8b-instruct-bf16 | H2 G2>G3 | +12.1 (p=9.87e-13) | +12.3 (p=9.57e-12) |
| llama3.1-8b-instruct-bf16 | H2 G2>G4 | +9.3 (p=2.68e-07) | +9.0 (p=2.99e-06) |
| llama3.1-8b-instruct-bf16 | H2 G2>R1 | +3.5 (p=0.017) | +3.3 (p=0.0272) |
| llama3.1-8b-instruct-bf16 | H2-null G4~G1 (TOST) | -0.4, equiv=False | -0.5, equiv=False |
| llama3.1-8b-instruct-bf16 | H3 N1P2 vs G2 | +30.6 (p=3.92e-52) | +32.5 (p=5.1e-53) |
| llama3.1-8b-instruct-bf16 | N1P3-N1P2 (exploratory) | +2.6 (p=7.52e-10) | +2.7 (p=3.51e-09) |
| olmo3-7b-instruct-bf16 | H1 G2>B1 | +22.2 (p=3.67e-28) | +22.9 (p=5.05e-27) |
| olmo3-7b-instruct-bf16 | H2 G2>G1 | +17.4 (p=3.15e-18) | +17.6 (p=9.59e-17) |
| olmo3-7b-instruct-bf16 | H2 G2>G3 | +21.2 (p=3.93e-27) | +21.6 (p=8.39e-25) |
| olmo3-7b-instruct-bf16 | H2 G2>G4 | +20.3 (p=7.45e-22) | +19.8 (p=1.44e-18) |
| olmo3-7b-instruct-bf16 | H2 G2>R1 | +4.4 (p=0.00189) | +5.2 (p=0.000649) |
| olmo3-7b-instruct-bf16 | H2-null G4~G1 (TOST) | -2.8, equiv=False | -2.2, equiv=False |
| olmo3-7b-instruct-bf16 | H3 N1P2 vs G2 | +12.6 (p=1.74e-11) | +14.6 (p=1.69e-14) |
| olmo3-7b-instruct-bf16 | N1P3-N1P2 (exploratory) | +3.4 (p=7.45e-13) | +3.5 (p=1e-11) |
| qwen2.5-7b-instruct-bf16 | H1 G2>B1 | +24.2 (p=5.1e-34) | +24.0 (p=9.11e-30) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G1 | +21.3 (p=5.04e-30) | +20.4 (p=3.23e-25) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G3 | +24.6 (p=3.61e-41) | +24.3 (p=9.52e-36) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G4 | +17.6 (p=5.18e-19) | +15.9 (p=1.09e-14) |
| qwen2.5-7b-instruct-bf16 | H2 G2>R1 | +8.0 (p=4.92e-08) | +7.7 (p=8.31e-07) |
| qwen2.5-7b-instruct-bf16 | H2-null G4~G1 (TOST) | +3.7, equiv=False | +4.4, equiv=False |
| qwen2.5-7b-instruct-bf16 | H3 N1P2 vs G2 | +15.3 (p=2.6e-15) | +17.8 (p=3.86e-19) |
| qwen2.5-7b-instruct-bf16 | N1P3-N1P2 (exploratory) | +0.6 (p=0.00623) | +0.4 (p=0.0289) |

Accuracy full -> kept:

- llama3.1-8b-instruct-bf16: B1 40.6->40.4; G1 46.4->46.9; G2 55.2->55.2; G3 43.6->43.5; G4 45.9->46.2; N1P2 85.5->87.5; N1P3 88.1->90.1; N1R 61.7->62.8; R1 51.9->52.1
- olmo3-7b-instruct-bf16: B1 45.5->45.6; G1 50.3->50.8; G2 68.2->69.0; G3 46.3->46.7; G4 47.4->48.8; N1P2 80.1->82.8; N1P3 83.5->86.3; N1R 60.2->61.9; R1 63.5->63.6
- qwen2.5-7b-instruct-bf16: B1 47.6->47.9; G1 50.6->51.4; G2 71.4->71.3; G3 47.3->47.7; G4 53.9->55.5; N1P2 86.8->89.4; N1P3 87.4->89.9; N1R 62.8->63.7; R1 63.9->64.2

## Set 'strict': 91 clusters dropped, 1311 items kept

| model | test | full | kept |
|---|---|---|---|
| llama3.1-8b-instruct-bf16 | H1 G2>B1 | +14.8 (p=7.56e-15) | +14.6 (p=1.63e-13) |
| llama3.1-8b-instruct-bf16 | H2 G2>G1 | +8.9 (p=1.53e-07) | +8.1 (p=7.03e-06) |
| llama3.1-8b-instruct-bf16 | H2 G2>G3 | +12.1 (p=9.87e-13) | +12.2 (p=2.01e-11) |
| llama3.1-8b-instruct-bf16 | H2 G2>G4 | +9.3 (p=2.68e-07) | +8.7 (p=7.03e-06) |
| llama3.1-8b-instruct-bf16 | H2 G2>R1 | +3.5 (p=0.017) | +3.3 (p=0.0293) |
| llama3.1-8b-instruct-bf16 | H2-null G4~G1 (TOST) | -0.4, equiv=False | -0.6, equiv=False |
| llama3.1-8b-instruct-bf16 | H3 N1P2 vs G2 | +30.6 (p=3.92e-52) | +33.0 (p=3.97e-54) |
| llama3.1-8b-instruct-bf16 | N1P3-N1P2 (exploratory) | +2.6 (p=7.52e-10) | +2.7 (p=3.49e-09) |
| olmo3-7b-instruct-bf16 | H1 G2>B1 | +22.2 (p=3.67e-28) | +23.0 (p=5.51e-27) |
| olmo3-7b-instruct-bf16 | H2 G2>G1 | +17.4 (p=3.15e-18) | +17.9 (p=5.31e-17) |
| olmo3-7b-instruct-bf16 | H2 G2>G3 | +21.2 (p=3.93e-27) | +21.9 (p=2.39e-25) |
| olmo3-7b-instruct-bf16 | H2 G2>G4 | +20.3 (p=7.45e-22) | +19.8 (p=2.6e-18) |
| olmo3-7b-instruct-bf16 | H2 G2>R1 | +4.4 (p=0.00189) | +5.2 (p=0.000716) |
| olmo3-7b-instruct-bf16 | H2-null G4~G1 (TOST) | -2.8, equiv=False | -1.9, equiv=False |
| olmo3-7b-instruct-bf16 | H3 N1P2 vs G2 | +12.6 (p=1.74e-11) | +14.7 (p=1.31e-14) |
| olmo3-7b-instruct-bf16 | N1P3-N1P2 (exploratory) | +3.4 (p=7.45e-13) | +3.5 (p=9.97e-12) |
| qwen2.5-7b-instruct-bf16 | H1 G2>B1 | +24.2 (p=5.1e-34) | +24.1 (p=1.27e-29) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G1 | +21.3 (p=5.04e-30) | +20.5 (p=3.41e-25) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G3 | +24.6 (p=3.61e-41) | +24.3 (p=1.53e-35) |
| qwen2.5-7b-instruct-bf16 | H2 G2>G4 | +17.6 (p=5.18e-19) | +15.8 (p=2.39e-14) |
| qwen2.5-7b-instruct-bf16 | H2 G2>R1 | +8.0 (p=4.92e-08) | +7.8 (p=6.18e-07) |
| qwen2.5-7b-instruct-bf16 | H2-null G4~G1 (TOST) | +3.7, equiv=False | +4.7, equiv=False |
| qwen2.5-7b-instruct-bf16 | H3 N1P2 vs G2 | +15.3 (p=2.6e-15) | +18.4 (p=3.74e-20) |
| qwen2.5-7b-instruct-bf16 | N1P3-N1P2 (exploratory) | +0.6 (p=0.00623) | +0.4 (p=0.0289) |

Accuracy full -> kept:

- llama3.1-8b-instruct-bf16: B1 40.6->40.5; G1 46.4->47.1; G2 55.2->55.0; G3 43.6->43.4; G4 45.9->46.3; N1P2 85.5->87.9; N1P3 88.1->90.5; N1R 61.7->63.2; R1 51.9->52.0
- olmo3-7b-instruct-bf16: B1 45.5->45.7; G1 50.3->50.7; G2 68.2->69.2; G3 46.3->46.6; G4 47.4->49.0; N1P2 80.1->83.1; N1P3 83.5->86.7; N1R 60.2->62.3; R1 63.5->63.8
- qwen2.5-7b-instruct-bf16: B1 47.6->47.6; G1 50.6->51.2; G2 71.4->71.2; G3 47.3->47.6; G4 53.9->55.6; N1P2 86.8->89.9; N1P3 87.4->90.4; N1R 62.8->63.8; R1 63.9->63.9
