# Patchability: When Does Dialogic Distillation Work?

> This document is maintained in the
> [KHub Knowledge Fabric](https://github.com/khub-ai/khub-knowledge-fabric/blob/main/docs/patchability.md)
> research repository and mirrored here for PatchBench contributors.
> If the two copies diverge, the KF version is canonical.

---

## The Core Question

DD works when the PUPIL has **latent perceptual capability that expert
vocabulary can unlock** — but is not currently using that capability because
it does not know what features to attend to.

DD fails when the PUPIL **genuinely cannot perceive** the relevant features:
not a vocabulary problem, but a hard sensory or resolution barrier.

These two failure modes look identical from the outside (low classification
accuracy) but have completely different causes:

| Failure type | Root cause | DD outcome |
|---|---|---|
| **Vocabulary gap** | PUPIL can see features but lacks terms | DD works |
| **Perception barrier** | Features physically unobservable | DD fails |

---

## The Four Patchability Dimensions

### G — Grounding Probe Rate

Fraction of expert-described features the VALIDATOR confirms as observable
in the PUPIL's modality.

| G | Interpretation |
|---|---|
| > 0.70 | Expert features observable — DD likely to work |
| 0.40–0.70 | Partial observability — DD may work with refinement |
| < 0.30 | Expert features unobservable — DD likely to fail |

### V — Vocabulary Divergence

How different is PUPIL's spontaneous description vocabulary from an expert's?

| V | Interpretation |
|---|---|
| High | Expert uses domain terms PUPIL never generates — high DD potential |
| Medium | Some overlap, some expert-specific terms |
| Low | PUPIL already uses near-expert vocabulary — small marginal gain |

### B — Zero-Shot Baseline Accuracy

How well does PUPIL perform on the confusable pair without DD?

| B | Interpretation |
|---|---|
| > 0.90 | Near-saturated — DD adds little |
| 0.40–0.75 | Genuine confusion — **DD sweet spot** |
| < 0.30 | Possible perception barrier (distinguish using G score) |

### E — Expert Convergence

Can a domain expert articulate clear, observable distinctions quickly?

| E | Interpretation |
|---|---|
| High | Expert answers immediately with specific visual features |
| Medium | Expert can distinguish but with caveats |
| Low | Expert hedges or requires non-visual context |

---

## Combined Assessment

```
High patchability:  G > 0.70  AND  V high  AND  0.40 < B < 0.75  AND  E high

No-go (any of):
  G < 0.30     perception barrier
  B > 0.90     already solved
  V low        no vocabulary gap to exploit
  E low        no stable expert vocabulary to distil
```

---

## Domain Assessments

### Confirmed Results

| Domain | G | V | B | E | Result |
|---|---|---|---|---|---|
| Birds (CUB-200) | ~0.85 | High | 33% | High | +50pp confirmed |
| Dermatology (HAM10000) | ~0.85 | High | 50–67% | High | +38–43pp confirmed |

### Predicted

| Domain | G | V | B | E | Prediction |
|---|---|---|---|---|---|
| Road surface (RSCD) | Medium-high | High | ~57% measured | High | High patchability |
| Candlestick patterns | High | High | ~50–65% est. | Medium-high | High patchability |
| SAR imagery (direct) | ~0.05 | Very high | Near random | High | **Very low** — modality barrier |

---

## Pre-Session Diagnostic Protocol

Before committing to a full DD experiment:

1. Collect 5 representative confusable-pair images
2. Expert description (15 min) → assess V and E
3. PUPIL free description (10 min) → compare to expert vocabulary
4. Grounding check (15 min) → compute G
5. Zero-shot accuracy (10 min) → compute B
6. Apply patchability matrix → go / no-go

Total: ~1 hour, ~25 images, one expert consultation.

---

## Theoretical Basis

```
PUPIL accuracy = f(latent_perceptual_capability, vocabulary_alignment)

DD increases:     vocabulary_alignment
DD cannot change: latent_perceptual_capability
```

G measures perceptual capability. V measures vocabulary alignment gap.
The grounding check is architecturally central because it keeps these two
separate — preventing rules that sound expert but require perception the PUPIL lacks.
