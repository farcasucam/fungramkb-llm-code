# Catálogo de scripts Python del proyecto

Análisis de todo el código necesario para las pruebas del paper 1 (guion, secciones 8–14), con su estado. Leyenda:

- **Hecho**: implementado y cubierto por `pytest` sobre el KB de juguete.
- **Hecho (GPU)**: implementado, pero solo se puede probar en la máquina con GPU.
- **Prompt Pxx**: depende de datos que aún no hemos visto (la exportación real) o de decisiones pendientes. El prompt para desarrollarlo está en `docs/PROMPTS.md`.

## 1. Datos de FunGramKB

| Script / módulo | Qué hace | Entrada → salida | Estado |
|---|---|---|---|
| `scripts/convert_export.py` | Convierte la exportación TSV de FunGramKB (Latin-1) al JSON canónico, repara tildes, ordena los guiones del Cognicón y fusiona las extensiones redactadas | `data/raw/*.tsv` + `data/extension/*.json` → `data/processed/fungramkb.json` | Hecho (P01) |
| `scripts/repair_lemmas.py` | Restaura tildes perdidas en lemas españoles (`?` → candidato con mayor frecuencia Zipf; wordfreq) | 168/170 reparados | Hecho |
| `data/extension/build_core_extension.py`, `build_lexicon_stubs.py` | 134 conceptos redactados (taxonomía intermedia, eventos, cualidades) y lemas EN/ES que faltaban; procedencia `authored-2026-10-05`, **pendiente de validación experta** | Hecho |
| `scripts/kb_report.py` | Auditoría de la KB (procedencia, cobertura de análisis, errores de la exportación) y muestra estratificada de 120 ítems para valoración experta de la NLG | Hecho |
| `kb/model.py` | Modelo en memoria: conceptos (#, +, $), herencia múltiple, lexicón ES/EN, Cognicón, Onomasticón | — | Hecho |
| `kb/loaders.py` | Carga, guarda y valida el JSON canónico | JSON ↔ `KnowledgeBase` | Hecho |
| `fgkb check-kb` | Informe de cobertura: postulados que no se pueden analizar, padres inexistentes | JSON → informe | Hecho |

## 2. COREL

| Script / módulo | Qué hace | Estado |
|---|---|---|
| `corel/corel.lark` + `parser.py` + `ast.py` | Gramática del postulado de significado (tesis, §3.1.7.2): operadores + y *, predicaciones ligadas, operadores de predicación, cuantificadores, conectores &, \| y ^, y satélites con predicaciones | Hecho (subconjunto). Ampliación: **P03** |
| `corel/facts.py` | Convierte postulados en propiedades y relaciones IS-A para el razonador | Hecho |
| `corel/verbalize.py` | Postulados → frases en inglés y español (para RAG, benchmark y LoRA) | Hecho; delega en `nlg.py` |
| `corel/nlg.py` | NLG por roles: voz activa/pasiva/oblicua/causativa, polaridad («never» / «typically does not»), género, ser/estar, contracciones, plural; descarta lo inexpresable | Hecho (P05) |
| `corel/gbnf.py` | Gramática GBNF de consultas COREL, para decodificación restringida (validada con xgrammar) | Hecho |

## 3. Razonamiento

| Script / módulo | Qué hace | Estado |
|---|---|---|
| `reasoner/asp.py` | Razonador ASP (clingo): herencia estricta y rebatible con especificidad (MicroKnowing), herencia múltiple con detección de conflictos, trazas verificables y comprobación de consistencia | Hecho |
| Expansión MicroKnowing a primitivos y razonamiento sobre dimensiones de cualidades (tesis, §5.3 y §5.5) | Profundizar la inferencia más allá de la herencia | **Prompt P04** |

## 4. Componentes de las 12 condiciones

| Condición | Módulo | Estado |
|---|---|---|
| Enlace de conceptos (todas) | `linking/linker.py` (lexicón + desambiguación tipo Lesk; admite un scorer por embeddings) | Hecho. spaCy y embeddings: **P07** |
| B0, B1 | `conditions/prompts.py` | Hecho |
| R1, R2 | `retrieval/rag.py` (TF-IDF por defecto, denso opcional) | Hecho. Retriever denso multilingüe: **P07** |
| G1, G2 | `graph/build.py` (postulados como nodos-predicación) y `ContextBuilder.full_context` (más marcos temáticos y guiones) | Hecho |
| G3 | `controls/generic_kg.py` (WordNet/OMW con el mismo presupuesto) | Hecho (requiere nltk). ConceptNet: **P08** |
| G4 | `controls/corrupt.py` (postulados permutados; taxonomía intacta) | Hecho |
| F1, F2 | `finetune/make_sft.py` (datos solo de conceptos vistos) y `finetune/train_lora.py` (TRL + PEFT, QLoRA) | Datos: Hecho. Entrenamiento: Hecho (GPU) |
| N1, N2 | `pipeline/neurosymbolic.py` (texto → COREL restringido → ASP → respuesta; N2 con bucle de verificación) | Hecho; validado con un backend oráculo (>97 %) |
| Ablaciones | `ABLATIONS` en `conditions/prompts.py` (ontología → + postulados → + marcos → + Cognicón) y la clave `ablation:` del YAML | Hecho |

## 5. Benchmark FGKB-Reason

| Script / módulo | Qué hace | Estado |
|---|---|---|
| `bench/generate.py` | Las 5 tareas del paper 1, gemelos ES/EN, gold del razonador, profundidad, trazas y distractores | Hecho |
| `bench/deep.py` | Suite profunda: prueba mínima y hechos requeridos (P13), bloques deep_real (profundidad ≥ 3 y encadenamiento de rellenos), novel (pseudopalabras), exceptions (excepción y excepción de excepción), counterfactual (+ controles), ablation (pares sin un hecho requerido), undetermined (+ controles de primos) | Hecho (P13–P15) |
| `bench/contrast.py` | Subconjunto de contraste: etiquetas equilibradas por (tarea, familia de formato, propiedad); **conjunto de análisis primario** | Hecho |
| `bench/splits.py` | Split por conceptos (30 % no vistos) y asignación dev / test_seen / test_unseen | Hecho |
| `bench/generate.balance` | Muestreo estratificado por tarea, profundidad y etiqueta, sin separar gemelos | Hecho |
| `scripts/paraphrase_items.py` | Paráfrasis con un LLM distinto de los evaluados y revalidación con el razonador | **Prompt P06** |
| `eval/agreement.py` | Hoja de anotación (400 ítems), κ de Cohen por plantilla y criterio de descarte < 0,7 | Hecho |
| `scripts/external_benchmarks.py` | Carga de XNLI-es, subconjuntos léxicos de SNLI/MNLI y COPA/xCOPA, más informe de cobertura | **Prompt P08** |

## 6. Ejecución y evaluación

| Script / módulo | Qué hace | Estado |
|---|---|---|
| `llm/backends.py` | Backends Mock, servidor OpenAI-compatible (vLLM serve), vLLM offline (con LoRA) y transformers | Hecho (GPU). Cambios de API de vLLM: **P10** |
| `runner.py` + `fgkb run` | Matriz modelos × condiciones × ítems, reanudable y con hash de configuración | Hecho |
| `eval/parse.py` | Normaliza respuestas libres (EN/ES) a etiquetas | Hecho |
| `eval/metrics.py` | Exactitud, macro-F1, curva por profundidad, tasa de contradicción ES↔EN, seguimiento de evidencia, cobertura y verificabilidad de N1 | Hecho |
| `scripts/validate_offline.py` | Validación sin LLM: V1 re-derivación del gold (100 %), V2 necesidad de los hechos requeridos (100 %), V3 mayoritaria, V4 test de artefactos solo-pregunta (agrupado por concepto), V5 potencia por simulación | Hecho |
| `scripts/pilot_analysis.py` | Análisis preregistrado del piloto: H1 G2 > B1, familia secundaria con Holm, sensibilidad a la evidencia, contrafactuales, excepciones y conceptos nuevos | Hecho |
| `scripts/run_pilot.sh` + `configs/pilot.yaml` | Piloto go/no-go en una GPU (2 modelos × 6 condiciones, ~22k generaciones, 1–3 h por modelo) | Listo para ejecutar |
| `scripts/n1p_oracle.py` | N1P sin LLM: cobertura de candidatos (sujeto, evento, objeto) y oráculo de slots (techo 99,8 %) | Hecho |
| `scripts/dev_parser_report.py` | Comparación de parsers N1/N1R/N1P frente a G2 en el split dev (cobertura, aciertos por slot, híbrido) | Hecho |
| `scripts/make_main_bench.py` | Benchmark del estudio principal (semilla 2027): marca el solapamiento con el piloto y pasa a dev lo que repite ítems de dev del piloto | Hecho |
| `configs/main_*.yaml` | Estudio principal (borrador; no ejecutar antes del preregistro) | Borrador |
| `bench/wording.py` + `scripts/make_wordings.py` | Redacciones alternativas W2 (inversión sujeto–verbo + sinónimos aprobados) y W3 (paráfrasis con un LLM ajeno, filtrada y auditada) | Hecho (W3 requiere el parafraseador) |
| `scripts/spark_paraphraser_up.sh` | Sirve el parafraseador W3 (Mistral-Small-3.2-24B) en la Spark, puerto 8003 | Hecho |
| `scripts/wording_analysis.py` | Robustez por redacción: exactitud W1/W2/W3, consistencia y contrastes G2−B1, N1P−G2 por redacción | Hecho |
| `configs/dev_wordings*.yaml`, `configs/main_wordings_*.yaml` | Comprobación en dev del piloto; robustez del estudio principal (borrador) | Listo / Borrador |
| `scripts/propose_lexicon.py` | Candidatos de nuevas unidades léxicas EN/ES desde WordNet/OMW para revisión experta (`docs/lexicon_candidates.tsv`) | Hecho |
| `scripts/apply_lexicon_expansion.py` | Añade las unidades aprobadas a la KB (`fungramkb_lex.json`, procedencia `lexicon-expansion-2026-10-07`) | Hecho |
| N1P2 (`pipeline/neurosymbolic.py`) | N1P con candidatos ampliados (eventos relacionales + todas las cualidades) | Hecho |
| `configs/dev_v4_{base,lex}_*.yaml` | Dev W1+W2+W3: G2, N1P, N1P2 con KB base y con léxico ampliado | Listo |
| `eval/stats.py` | IC por bootstrap, McNemar exacto y Holm-Bonferroni | Hecho |
| `analysis/report.py` + `fgkb report` | Tablas LaTeX (booktabs) y figura de profundidad en `paper/` (sincronizada con Overleaf) | Hecho |
| `scripts/contamination_probe.py` | Sondeo de contaminación: ¿completa el modelo postulados de FunGramKB? | **Prompt P09** |
| `scripts/error_analysis.py` | Muestras de error por tipo (enlace, parsing, cobertura) para la sección Analysis | **Prompt P11** |
| `scripts/slurm/*.sh`, `scripts/serve_vllm.sh` | Lanzamiento en clúster o servidor | **Prompt P10** |

## Orden de trabajo recomendado (semanas 1–4)

1. P01: convertir la exportación y ejecutar `fgkb check-kb`. El objetivo es que menos del 5 % de los postulados no se puedan analizar. Si hay más, se hace P03 antes de seguir.
2. `fgkb bench` con `configs/bench.yaml`, luego P06 (paráfrasis) y la hoja de anotación humana.
3. `fgkb run` con B0, B1, G1, G2, G3, G4 y N1 sobre 2 modelos: es la matriz mínima del go/no-go del 29 de noviembre.
4. `fgkb sft-data`, luego `train_lora` (3 semillas), y después F1/F2, R1/R2, N2 y las ablaciones.
5. `fgkb report` para generar las tablas y figuras del paper.
