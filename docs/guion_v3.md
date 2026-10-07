# Integración de semántica profunda FunGramKB en modelos fundacionales de lenguaje

*Guion del proyecto. Versión 3, del 5 de octubre de 2026. Sustituye a la versión 2 del 4 de octubre.*

**Cambios en la v3.** La v3 incorpora lo aprendido al trabajar con la exportación real de FunGramKB y con el código ya en marcha.

- **Datos reales.** Se describen la exportación real y la extensión redactada de la KB (sección 8).
- **Benchmark.** Se dan las cifras reales de FGKB-Reason y de la suite profunda (sección 12), y se introduce el *subconjunto de contraste*, que pasa a ser el conjunto de análisis primario (12.4).
- **Validación.** Se informa de la validación offline ya hecha, V1–V7 (sección 14.5).
- **Análisis.** Se concreta el análisis preregistrado del piloto (16.1).
- **Viabilidad.** Se actualizan la viabilidad (20), con el piloto listo para GPU u Ollama, el estado del código (23), los riesgos (24) y el cronograma (25).
- **Estado y limitaciones.** Se añade la sección 29, con el estado de calidad y las limitaciones abiertas.

Las hipótesis, condiciones y métricas de la v2 no cambian.

## 0. Ficha del proyecto

| | |
|:-|:-|
| Investigador principal | Francisco J. Arcas Túnez (UCAM) |
| Primer paper | ACM Transactions on Intelligent Systems and Technology (TIST), número especial «Knowledge-Informed Large Language Models: Integrating Physical Laws, Symbolic Reasoning, and Data-Driven Learning». Fecha límite: 15 de enero de 2027. |
| Afirmación central | La semántica profunda de FunGramKB mejora el razonamiento profundo de LLM abiertos: inferencias de varios pasos, con excepciones y que combinan tipos de conocimiento. Y lo mejora porque el modelo razona con ese conocimiento, no porque recuerde mejor ni porque reciba más contexto. |
| Redacción | LaTeX en Overleaf (plantilla acmart), en inglés científico británico (en-GB). |
| Código | Python, repositorio fungramkb-llm (copia en la carpeta del proyecto). Será público cuando se envíe el paper. 46 tests en verde. |
| Datos | Exportación TSV de FunGramKB (dominio GlobalCrimeTerm: delincuencia, drogas, terrorismo y justicia) más una extensión redactada, pendiente de validación experta (sección 8). |
| Modelos | Open-weight de 7–14B, adaptados con LoRA/QLoRA. Opcionalmente, uno de unos 70B solo en inferencia. |
| Hitos críticos | Preregistro: 15 nov 2026. Go/no-go: 29 nov 2026. |

## 1. Idea general

El proyecto investiga si incorporar a los LLM una representación semántica profunda, explícita y formalizada (FunGramKB y su lenguaje COREL) mejora capacidades como la comprensión semántica, la composicionalidad, la inferencia, el razonamiento multi-hop, la consistencia y el conocimiento procedimental.

FunGramKB no sustituye la representación neuronal de los LLM: la complementa con una capa conceptual explícita y verificable. COREL actúa como representación intermedia entre el lenguaje natural y el razonamiento simbólico.

Flujo conceptual: texto → LLM → semantic parsing → COREL → Ontología / Cognicón / Onomasticón → postulados → razonador → inferencias → COREL validado → LLM → lenguaje natural.

## 2. Fundamento teórico

Componentes de FunGramKB que usa el proyecto:

- **Ontología**, con tres niveles: metaconceptual (#), básico (+) y terminal ($).
- **Cognicón**, que recoge el conocimiento procedimental mediante guiones.
- **Onomasticón**, con entidades y conocimiento específico.
- **Postulados de significado** en COREL, con predicaciones estrictas (+) o rebatibles (*).
- **Marcos temáticos**, con las preferencias de selección de los eventos.
- **Lexicones** paralelos en inglés, español e italiano.
- **Gramaticón** y el parser ARTEMIS, basado en la RRG.

El motor de razonamiento de la tesis (Arcas Túnez, 2008, cap. 5) es MicroKnowing: herencia múltiple y no monótona, con predicaciones rebatibles tratadas como reglas con excepciones. Es la base del razonador ASP del proyecto y del gold standard.

## 3. Preguntas de investigación e hipótesis (sin cambios respecto a la v2)

Pregunta principal: *Can explicit deep semantic representations complement the distributed representations of foundation language models to improve deep semantic reasoning, consistency and knowledge-grounded inference?*

H1 y H2 son las hipótesis primarias y se preregistran.

| RQ | Hipótesis falsable | Experimento |
|:-|:-|:-|
| RQ1 (primaria) | H1: la ventaja de G2 sobre B1 crece con la profundidad de la prueba; la interacción condición × profundidad es positiva. En el piloto: G2 > B1 en el subconjunto de contraste profundo. | Matriz sobre FGKB-Reason, estratificada por profundidad |
| RQ2 (primaria) | H2: en el subconjunto profundo, G2 supera a G1 y a G3 con el mismo presupuesto, y G4 no supera a G1. | Comparaciones pareadas con Holm |
| RQ3 | H3: la ventaja de G2 se mantiene en conceptos nuevos y en KB contrafácticas, y la respuesta depende causalmente de los hechos necesarios. | R-B, R-C y R-F |
| RQ4 | H4a: RAG/GraphRAG gana en conceptos no vistos y LoRA en los vistos. H4b: el pipeline neuro-simbólico gana en profundidad y consistencia. H4c: LoRA entrenado con d ≤ 2 no generaliza a d = 3–4. | Comparación por canal; R-H |
| RQ5 | H5: menos contradicciones, mejor precisión de pasos y citas, y mejor abstención. | R-I, R-J y R-K |
| RQ6 | H6: la brecha entre español e inglés se reduce con FunGramKB. | Gemelos ES/EN |

## 4. Objetivos

**Objetivo general:** diseñar y evaluar una arquitectura híbrida LLM + FunGramKB + razonamiento simbólico, y demostrar empíricamente en qué medida mejora el razonamiento profundo.

| # | Objetivo | Paper |
|:-|:-|:-|
| O1 | Comparar estrategias de integración (prompting, RAG, GraphRAG, LoRA y neuro-simbólica) con controles de cantidad de información | 1 |
| O2 | Comparar con LLM convencionales, RAG y KG genéricos | 1 |
| O3 | Crear FGKB-Reason, con gold formal y validado | 1 y 3 |
| O4 | Construir un razonador formal con pruebas verificables | 1 |
| O5 | Construir un parser LLM → COREL | 2 |
| O6 | Validar formalmente el COREL que genera el LLM | 1 y 2 |

## 5. Hoja de ruta de publicaciones (sin cambios)

| Paper | Contenido | Destino | Plazo |
|:-|:-|:-|:-|
| 1 | ¿Mejora FunGramKB el razonamiento profundo? ¿Por qué canal? | ACM TIST (número especial KI-LLM) | 15 ene 2027 |
| 2 | Text → COREL: parser, corpus y equivalencia formal | Computational Linguistics, NLE, LREC-COLING o *SEM | 2027 |
| 3 (opcional) | Benchmark ampliado, con las 10 tareas | Datasets & Benchmarks o LRE | 2027–2028 |
| ES | Resultados ES/EN | Procesamiento del Lenguaje Natural (SEPLN) | Opcional |

## 6. Text → COREL como problema central

En el paper 1 el LLM genera un subconjunto de COREL (una predicación con roles), restringido por una gramática GBNF, como paso de N1/N2. Con un parser perfecto, la parte simbólica de N1 acierta el 100 % de los ítems profundos expresables (V7, sección 14.5). Por tanto, cualquier error de N1 se deberá al análisis del LLM, lo que sitúa el paper 2 justo en el cuello de botella. El parser completo pasa al paper 2.

## 7. No se entrena un modelo desde cero

Se adaptan modelos open-weight ya entrenados con LoRA/QLoRA, en modelos de 7–14B.

## 8. Estrategia de datos (actualizada con los datos reales)

### 8.1 La exportación real

`data/raw/*.tsv` contiene las tablas siguientes, en Latin-1:

- **concept**, con 377 conceptos.
- **hypernym** (herencia simple).
- **word**, con el lexicón ES/EN/IT.
- **cognicon**, con 10 guiones.
- **thematic_schemata**, con los marcos por metaconcepto.
- Otras tablas que no se usan.

El conversor P01 produce el JSON canónico con estas cifras:

- **584 conceptos** y **1885 unidades léxicas** (es 783, en 742, it 360).
- **10 guiones**, con 136 pasos ordenados topológicamente a partir de las relaciones Before.
- **432 postulados**, de los que **431 se analizan (99,8 %)**.
- **302 hechos de propiedad** y **334 enlaces IS-A** leídos de las clasificaciones BE_00.

**Problemas detectados en la exportación**, que se comunicarán al equipo de FunGramKB como auditoría de la KB:

1. **Tildes perdidas** en los lemas españoles. Se han reparado 168 de 170 por frecuencia léxica; los 2 irrecuperables se excluyen.
2. **Un postulado mal formado**: el de +CONTRACT_KILLER_00, con un paréntesis desequilibrado.
3. **Un lema inglés archivado como español** («weapon» en +WEAPON_00).
4. **Marcos temáticos más estrechos que los postulados.** Los marcos por defecto heredados de los esquemas de metaconcepto no admiten roles que sí usan los postulados (por ejemplo, Agent en +STORE_00).

### 8.2 Ampliaciones de la gramática COREL

El conversor amplía la gramática para admitir construcciones reales de la exportación:

- variables correferentes como relleno, como en `(f3: x1)Scene`;
- predicaciones ligadas entre paréntesis como relleno;
- preferencias de selección negadas;
- primitivos semánticos (`sp`).

La extracción de hechos resuelve la **correferencia de variables entre predicaciones**. Por ejemplo, en `(x3: +ALCOHOL_00)` … `(x3)Theme` se obtiene «el contrabandista vende alcohol». Además, ya no lee como IS-A las clasificaciones disyuntivas («x es D o E»).

### 8.3 Extensión redactada (escasez de datos)

La exportación sola daba solo **122 pares concepto-propiedad de profundidad ≥ 3**. Por eso se ha redactado una extensión siguiendo las convenciones de la tesis:

- **134 conceptos** con procedencia `authored-2026-10-05`: taxonomía intermedia (organismo, animal, humano, grupos, lugares, artefactos, sustancias), unos 70 eventos y cualidades.
- **31 conceptos solo léxicos** (`stub-lemma-only`), sin postulado.
- **Lemas EN/ES** para conceptos exportados que no los tenían.

La extensión **nunca sobrescribe** un concepto exportado. Los resultados se informarán en dos estratos (V6): en el subconjunto de contraste, **476 de 737 ítems con prueba (65 %) usan solo conocimiento exportado**. **Pendiente: validación experta de la extensión** (Paco).

### 8.4 Resto de la estrategia (como en la v2)

- **Paráfrasis** con un LLM distinto de los evaluados, revalidadas con el razonador.
- **Split por conceptos:** el 30 % no se ve en el entrenamiento.
- **Split por profundidad para LoRA:** d ≤ 2 en entrenamiento y d = 3–4 en test.
- **Datos para LoRA:** 20 000–50 000 pares, solo de conceptos vistos.

## 9. Arquitectura propuesta

**Componentes:**

- Enlace de conceptos compartido por todas las condiciones. Ahora admite lemas con guion, como «q-fever».
- Razonador ASP (clingo) con herencia no monótona y prueba mínima.
- Grafo con postulados como nodos-predicación.
- GBNF/XGrammar para la decodificación restringida.

**Contexto de G2.** El contexto se construye en este orden y con estas reglas:

1. Cadena IS-A y postulados del concepto.
2. Expansión de un anillo a través de los rellenos de rol, que da GraphRAG de dos saltos. Con ella, la evidencia necesaria aparece en el contexto en el 97–100 % de los ítems profundos (antes era el 73 %).
3. Marcos y guiones, solo si la pregunta los menciona, con un máximo del 30 % del presupuesto.

**Ítems con KB modificada.** Los ítems de conceptos nuevos, contrafácticos y ablación usan exactamente su propia KB, mediante `ContextBuilder.for_item` y el mismo mecanismo en N1. G4 añade solo los conceptos nuevos del parche y nunca las ediciones de conceptos existentes, porque eso filtraría el postulado verdadero.

## 10. El papel del razonamiento simbólico

- RAG recupera conocimiento.
- El KG representa relaciones.
- FunGramKB representa conocimiento conceptual profundo.
- El razonador opera formalmente sobre ese conocimiento y es además la fuente del gold.
- El LLM interpreta la pregunta y expresa la respuesta.

## 11. Sistemas, baselines y controles (sin cambios)

Hay 12 condiciones, todas con el mismo presupuesto máximo de unos 1500 tokens:

- **Baselines:** B0 (zero-shot) y B1 (CoT).
- **Contexto:** R1 (RAG textual) y R2 (RAG en COREL).
- **Grafo:** G1 (solo IS-A), G2 (FunGramKB completo), G3 (WordNet/ConceptNet) y G4 (KB corrupta, con la taxonomía intacta).
- **Pesos:** F1 (LoRA) y F2 (LoRA + G2).
- **Neuro-simbólico:** N1 (texto → COREL → ASP) y N2 (N1 con bucle de verificación).

Nota de la v3: el presupuesto es un máximo. El uso real se registra por ítem (`ctx_tokens`) y entra como covariable. En la prueba en seco, R1 usa unos 470 tokens de media y G2 unos 120.

## 12. Benchmark FGKB-Reason (cifras reales)

### 12.1 Razonamiento profundo (definición de la v2)

- **Profundidad:** número de aplicaciones de reglas en la prueba mínima. Cuentan el paso IS-A, el postulado, el bloqueo por excepción y el encadenamiento por relleno.
- **Ítem profundo:** d ≥ 3, o composición de tipos de razonamiento.

### 12.2 Núcleo

Hay 22 887 ítems ES + EN. Se generan con semilla fija y de forma reproducible (`fgkb bench --deep`).

| Tarea | Ítems (ES + EN) | Nota |
|:-|:-|:-|
| Implicación | 7184 | 3 clases |
| Multi-hop | 4372 | Los negativos IS-A usan ahora la misma categoría con otra entidad (par de contraste) |
| Consistencia | 6504 | Corregido un pair_id que mezclaba polaridades |
| Procedimental | 730 | Nombres españoles de los 10 guiones |
| Anclaje | 41 | Escaso: el dominio tiene poca polisemia nominal; las opciones se barajan |

### 12.3 Suite profunda

Son 4056 ítems (2028 EN + 2028 ES).

| Bloque | EN | Etiquetas | Explicación alternativa que descarta |
|:-|:-|:-|:-|
| Profundo real (d ≥ 3 y encadenamiento por rellenos) | 555 | 409 sí / 146 no | Mejora solo en un paso |
| Conceptos nuevos (pseudopalabras) | 545 | 248 sí / 57 no / 240 indet. | Recuerdo memorizado |
| Contrafácticos (afectado + control) | 193 | 85 sí / 108 no | Respuesta por el prior |
| Excepciones (excepción y excepción de la excepción) | 126 | 64 / 62 | Razonamiento monótono |
| Indeterminados (propiedades de primos) | 275 | indet. | Alucinación |
| Controles de primos | 112 | sí | Atajo por propiedad |
| Ablación de evidencia | 222 | indet. (gemelo intacto: sí/no) | Independencia del contexto |

**Cambios de diseño en la v3,** detectados por el test de artefactos V4:

- **Excepciones:** se dan siempre las dos definiciones, se pregunte por la excepción o por la excepción de la excepción.
- **Contrafácticos:** cada uno tiene un control con el mismo escenario y otra propiedad no afectada.
- **Conceptos nuevos:** cada uno tiene controles «indeterminados» con propiedades de otros padres.
- **Indeterminados:** se emparejan con el primo que sí tiene la propiedad, y se exige que el antepasado común sea específico.

### 12.4 Subconjunto de contraste (conjunto de análisis primario, nuevo en la v3)

Un clasificador que solo ve la pregunta puede aprender **priors de propiedad**: por ejemplo, que «… está vivo» casi siempre es «sí». Por eso el análisis primario usa un subconjunto donde, para cada combinación de tarea, familia de formato y propiedad preguntada, cada etiqueta aparece por igual. Los gemelos ES/EN se mantienen juntos.

| Tarea | Ítems por idioma |
|:-|:-|
| Profunda | 951 (443 sí / 146 no / 362 indet.) |
| Implicación | 1228 |
| Multi-hop | 1298 |
| Consistencia | 476 |

En la tarea profunda, el subconjunto incluye todos los bloques: 149 de profundo real, 206 de conceptos nuevos, 124 de excepciones, 100 contrafácticos, 148 de ablación, 112 indeterminados y 112 controles.

## 13. Gold standard (como en la v2, con resultados)

- **Nivel 0 — gold formal.** Etiqueta de 3 valores, fuerza, prueba mínima, hechos necesarios, profundidad, tipos y variante de KB. Ya implementado; cada ítem profundo guarda `prop`, `required_facts` y `kb_patch`.
- **Nivel 1 — gold verificado por expertos** (600 ítems). Las mismas cuatro preguntas y los mismos indicadores (κ ≥ 0,7; validez ≥ 95 %). **Ya hay una primera muestra** de 120 ítems estratificados por bloque, con columnas de fluidez EN/ES y fidelidad a la KB (`docs/nlg_audit_sample.tsv`).
- **Nivel 2 — gold externo**: benchmarks externos.

**Validación del razonador:** re-derivación independiente (V1 = 100 %) y necesidad de los hechos de la prueba (V2 = 100 %); ver 14.5. No hay LLM-as-judge en ningún nivel.

## 14. Tipos de test para validar los resultados

Las tablas 14.1–14.4 se mantienen como en la v2:

- **Validez del benchmark:** V1–V5.
- **Validez interna:** V6–V9.
- **Razonamiento profundo:** R-A a R-K.
- **Validez externa.**

### 14.5 Resultados de la validación offline (nuevo en la v3; `scripts/validate_offline.py`, `docs/validation_report.md`)

| Test | Resultado | Criterio | Estado |
|:-|:-|:-|:-|
| V1 Re-derivación del gold con un razonador nuevo, sobre la KB de cada ítem | 1695/1695 (100 %) | ≥ 95 % | ✔ |
| V2 Necesidad de los hechos requeridos (al quitar uno cambia la respuesta) | 200/200 (100 %) | Pruebas mínimas | ✔ |
| V3 Clase mayoritaria (profunda, contraste) | 0,466 | ≤ 0,50 en 3 clases | ✔ |
| V4 Solo-pregunta (TF-IDF + regresión logística, CV agrupada por concepto), conjunto completo | Profunda 0,65 frente a 0,45; consistencia 0,89 frente a 0,50 | ≤ mayoritaria + 5 puntos | ✘ en el conjunto completo |
| V4 en el subconjunto de contraste | Profunda 0,43 frente a 0,47; implicación 0,36 frente a 0,50; multi-hop 0,49 frente a 0,53; consistencia 0,54 frente a 0,50 | ≤ mayoritaria + 5 puntos | ✔ (de ahí que sea el conjunto primario) |
| V5 Potencia (simulación con efectos aleatorios de ítem, gemelos como clúster, Holm sobre 6 comparaciones) | 951 clústeres: +5 puntos → 0,97 (α = 0,05) y 0,90 (Holm); +8 puntos → 1,00 | ≥ 0,8 | ✔ |
| V6 Procedencia | El 65 % de los ítems de contraste con prueba usan solo conocimiento exportado | Informar los 2 estratos | ✔ |
| V7 Techo simbólico de N1 (parser perfecto) | 1645/1645 (100 %), incluidas las KB modificadas | — | ✔ |
| Evidencia en el contexto de G2 | 97–100 % de los ítems por bloque | — | ✔ |

## 15. Prompts centrados en razonamiento profundo (sin cambios)

**Principios:**

- hechos numerados;
- salida JSON con steps y confidence;
- opción explícita de «indeterminado»;
- instrucción de prioridad («si los hechos contradicen lo que sabes, sigue los hechos»);
- 3 variantes de redacción por familia;
- sin ejemplos resueltos del mismo tipo de prueba.

**Familias:** PR1 (cadena explícita), PR2 (concepto nuevo), PR3 (contrafáctico), PR4 (excepciones), PR5 (indeterminado), PR6 (marcos y guiones) y PR7 (consistencia global).

**Pendiente:** P16, que implementa PR1–PR7 en el código.

## 16. Modelos, métricas y protocolo

Las métricas y el protocolo estadístico son los de la v2:

- **Análisis primario** con un modelo logístico de efectos mixtos (condición × profundidad + idioma) e interceptos aleatorios por concepto, plantilla y modelo.
- **Comparaciones pareadas** con McNemar y Holm, y bootstrap por concepto.

Cambio en la v3: todo se calcula sobre el **subconjunto de contraste**, y el conjunto completo se informa como secundario.

### 16.1 Análisis preregistrado del piloto (`scripts/pilot_analysis.py`)

- **H1 (una prueba por modelo):** exactitud(G2) > exactitud(B1) en el contraste profundo. Se contrasta con una prueba t pareada por clúster (gemelos ES/EN), unilateral, más McNemar exacto en EN e IC por bootstrap.
- **Familia secundaria con Holm:** G2 > G1, G2 > G4, G2 > R1 y N1 > G2. Además, G2 > B1 solo en conceptos no vistos.
- **Diagnósticos «razonar frente a recordar»:**
  - sensibilidad a la evidencia: acierta en el gemelo intacto y pasa a «indeterminado» al quitar el hecho;
  - contrafácticos afectados frente a controles;
  - excepciones;
  - conceptos nuevos.
- El análisis se ha validado con resultados sintéticos de efecto conocido: lo detecta, con p < 0,001.

## 17. Ablaciones (sin cambios)

Ontología → + postulados → + marcos → + Cognicón → + Onomasticón → + razonador. Se analizan por tipo de razonamiento.

## 18. Contribución científica esperada

1. Un marco comparativo controlado de las cuatro familias de integración.
2. **FGKB-Reason**, con gold formal validado y suite profunda. Novedad metodológica de la v3: el **subconjunto de contraste por propiedad** con test de artefactos.
3. Un pipeline neuro-simbólico verificable, con techo simbólico del 100 %.
4. Evidencia de que la mejora es razonamiento y no recuerdo.
5. Una auditoría de la calidad de la exportación de FunGramKB (sección 8.1).

## 19. Resultados esperados (sin cambios)

Se esperan mejoras concentradas en d ≥ 3, excepciones, conceptos nuevos, contrafácticos, consistencia y abstención, y un posible efecto techo en un paso.

## 20. Viabilidad (actualizada)

- **Sin entrenar desde cero.** Todo el pipeline funciona de principio a fin con la KB real; hay una prueba en seco con backend mock sobre 400 ítems de contraste y 6 condiciones.
- **Piloto go/no-go listo** (`scripts/run_pilot.sh`, `configs/pilot.yaml`):
  - 2 modelos (Qwen2.5-7B-Instruct y Llama-3.1-8B-Instruct) × 6 condiciones (B1, G1, G2, G4, R1 y N1) × unos 1900 ítems = unas 22 000 generaciones;
  - con vLLM se estiman 1–1,5 h por modelo en una A100 o 2–3 h en una RTX 4090;
  - la ejecución es reanudable.
- **Alternativa sin vLLM:** `configs/pilot_ollama.yaml`, con Ollama local y API compatible con OpenAI. Los modelos cuantizados deben informarse como tales.
- **Validación humana:** la muestra de 600 ítems más la revisión de la extensión redactada.

## 21. Posicionamiento editorial (sin cambios)

- **Opción principal:** ACM TIST, número especial KI-LLM. Envío el 15 ene 2027, primera respuesta el 15 abr, revisión el 15 jun y publicación en el cuarto trimestre de 2027.
- **Alternativa:** Intelligent Computing, «Foundation Models Beyond Text» (encaje bajo).
- **Otras:** Neurosymbolic AI, KBS, IP&M y NLE.

## 22. Redacción del paper (sin cambios)

acmart (acmsmall, screen, review), en-GB, Overleaf ↔ GitHub en la carpeta paper/.

**Estructura:** Introduction, Background, Related Work, Method, The FGKB-Reason Benchmark (con la sección nueva «Contrast subset and artefact control»), Experimental Setup, Results, Analysis, Discussion & Limitations y Conclusion.

## 23. Desarrollo del software (estado a 5 oct 2026)

**Hecho:**

- **Datos:** conversor P01, reparación de lemas y extensión de la KB.
- **COREL:** ampliaciones de la gramática y correferencia de variables.
- **NLG (P05):** voz activa, pasiva, oblicua y causativa; polaridad con «never» y «typically … not»; ser/estar; género; contracciones; plural. Las frases inexpresables se descartan.
- **Suite profunda:** P13 (prueba mínima) y P14/P15, con controles.
- **Análisis:**
  - subconjunto de contraste;
  - GraphRAG de dos saltos;
  - G4 y N1 sobre KB modificadas;
  - validación offline V1–V7;
  - informe de auditoría de la KB;
  - análisis preregistrado del piloto;
  - scripts del piloto para vLLM y Ollama.

**Pendiente:**

- P16 (prompts PR1–PR7 con salida JSON y puntuación de citas);
- P17 (modelo mixto con statsmodels/lme4 y plantilla de preregistro);
- P03 (resto de COREL);
- P06 (paráfrasis), P07 (retriever denso) y P08 (benchmarks externos).

## 24. Riesgos y mitigaciones (actualizado)

| Riesgo | Prob. | Mitigación |
|:-|:-|:-|
| Circularidad | Alta | Gold de 3 niveles, controles G1/G3/G4, conceptos nuevos y benchmarks externos |
| Artefactos de plantilla (confirmado por V4 en el conjunto completo) | — | Mitigado: el subconjunto de contraste deja el solo-pregunta por debajo de la mayoritaria |
| Conceptos redactados no validados (35 % de las pruebas) | Media | Revisión experta; resultados por estratos de procedencia |
| NLG imperfecta (por ejemplo, «deal with an illness») | Media | Muestra de valoración experta; los ítems con fluidez < 3 se descartan antes del preregistro |
| Dominio único (delincuencia y drogas) | Alta | Se declara como limitación; validez externa con NLI, COPA y XNLI-es |
| Anclaje con muy pocos ítems (41) | Alta | Se informa como descriptivo; no entra en las hipótesis |
| Efecto techo en un paso | Alta | Análisis en el subconjunto profundo |
| COREL difícil para el LLM | Alta | GBNF y techo simbólico del 100 % (el error será del parser) |
| Falta de tiempo | Media | Prioridad: piloto con 2 modelos sobre el contraste profundo |

## 25. Cronograma (actualizado)

| Bloque | Fechas | Estado |
|:-|:-|:-|
| Conversor P01, enlazador y extensión de la KB | 5–18 oct 2026 | Hecho |
| Validación del razonador y P13 | 12–25 oct | Hecho (V1 y V2 = 100 %) |
| Núcleo y suite profunda (P14, P15) y contraste | 19 oct – 8 nov | Hecho |
| Validación humana (nivel 1) y revisión de la extensión | 6 oct – 15 nov | Pendiente (Paco) |
| P16 (prompts PR1–PR7) y piloto pequeño | 2–13 nov | Piloto listo; falta P16 |
| Preregistro en OSF | 15 nov | Análisis ya escrito |
| Matriz mínima: piloto con 2 modelos | 16–29 nov | Listo para GPU u Ollama |
| Go/no-go | 29 nov | |
| Matriz completa, LoRA y R-F a R-K | 30 nov – 20 dic | |
| Análisis P17 | 7–27 dic | |
| Redacción en Overleaf | 16 nov – 10 ene 2027 | |
| Envío a ACM TIST | 15 ene 2027 | |

## 26. Posibles contribuciones a medio plazo (sin cambios)

- un semantic adapter;
- un parser Text → COREL;
- un compilador COREL → lenguaje natural;
- un razonador neuro-simbólico;
- un benchmark de semántica profunda;
- un corpus Text ↔ COREL;
- agentes basados en conocimiento conceptual y procedimental.

## 27. Referencias de partida

Las mismas de la v2: tesis de 2008; Introducción a FunGramKB; Meaning postulates; La gramática de COREL; ARTEMIS; Grammaticon; Frame Semantics en LLM (*SEM 2025, ACL 2026, EMNLP 2025); inyección de KG; LOGicalThought; Ontology-Grounded, Reasoner-Verified Benchmarks; AMR-LDA; LLMs4OL; y las dos CFP.

**Pendientes de añadir:**

- GraphRAG (Edge et al., 2024);
- surveys de KG + LLM;
- LLM + ASP;
- decodificación restringida;
- **conjuntos de contraste y artefactos de anotación** (Gardner et al., 2020; Gururangan et al., 2018; Poliak et al., 2018), por verificar.

## 28. Resultado científico que se pretende demostrar (sin cambios)

La semántica profunda mejora el razonamiento **profundo**, con una ventaja que crece con la longitud de la prueba (R-A, R-D, R-E). Esa mejora procede de razonar con el conocimiento aportado y no de recordarlo (R-B, R-C, R-F), y supera a una taxonomía y a un KG genérico con el mismo presupuesto (G1, G3, G4).

## 29. Estado de calidad de la propuesta (ciclo de revisión del 5 oct 2026)

Puntuación sincera de 1 a 10:

| Criterio | Nota | Base | Qué falta para llegar a 9–10 |
|:-|:-|:-|:-|
| Rigor científico | 8 | Gold re-derivado al 100 %; pruebas mínimas necesarias al 100 %; artefactos controlados (contraste); análisis preregistrado y probado; estratos de procedencia; muestra para validación experta | Validación experta de la extensión y de la NLG; segundo dominio o benchmarks externos |
| Viabilidad técnica | 8 | Pipeline completo con datos reales; 46 tests; scripts del piloto para vLLM y Ollama con tiempos estimados; N1 sobre KB modificadas | Ejecutar el piloto en GPU; implementar P16 |
| Resultados significativos | 6 | Potencia de 0,90–0,97 para +5 puntos; techo simbólico del 100 %; benchmark sin atajos. No hay todavía ninguna ejecución con un LLM real, porque este entorno no tiene GPU ni acceso a modelos | Ejecutar scripts/run_pilot.sh (o la versión Ollama) y scripts/pilot_analysis.py: si H1 sale con p < 0,05 en los 2 modelos y la sensibilidad a la evidencia de G2 > B1, la nota sube a 8 o más |
