"""
schema.py — PatchBench manifest and result schema.

Stable versioned contract for benchmark manifests and probe result reports.
Breaking changes increment the major version.

Schema version: 1.0
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

SCHEMA_VERSION = "1.0"

DIFFICULTY_EASY   = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD   = "hard"

VERDICT_GO      = "go"
VERDICT_PARTIAL = "partial"
VERDICT_NO_GO   = "no-go"


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

@dataclass
class ManifestImage:
    """One image in a benchmark manifest."""
    image_id:   str
    filename:   str
    true_class: str
    difficulty: str = DIFFICULTY_MEDIUM
    notes:      str = ""
    metadata:   Dict = field(default_factory=dict)  # domain-specific fields


@dataclass
class FeatureQuery:
    """A feature detection query authored by the TUTOR."""
    feature_id:     str
    question:       str
    diagnostic_for: str   # which class this feature being present indicates
    difficulty:     str = DIFFICULTY_MEDIUM


@dataclass
class Precomputed:
    """TUTOR and VALIDATOR outputs pre-committed to the manifest.

    These are served directly to the runner so contributors only need
    API credentials for their own PUPIL model.

    Set recompute=True in the runner to regenerate these from scratch.
    Use --save-precomputed to populate this section and commit the result.
    """
    tutor_model:       str
    validator_model:   str
    generated:         str                        # ISO date
    tutor_descriptions: Dict[str, str]            = field(default_factory=dict)
    # image_id -> description string
    feature_queries:   List[FeatureQuery]         = field(default_factory=list)
    validator_answers: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    # image_id -> {feature_id -> bool}
    seed_rules:        Optional[Dict[str, dict]]  = None
    # class_name -> rule dict, one per class (preferred)
    seed_rule:         Optional[dict]             = None
    # legacy single-rule field — superseded by seed_rules


@dataclass
class BenchmarkManifest:
    """A PatchBench probe benchmark manifest."""
    benchmark_id:   str
    schema_version: str
    version:        str
    domain:         str
    created:        str
    pair_id:        str
    class_a:        str
    class_b:        str
    description:    str
    images:         List[ManifestImage]  = field(default_factory=list)
    precomputed:    Optional[Precomputed] = None
    images_dir:     str = "images/"      # relative to manifest file

    @property
    def n_images(self) -> int:
        return len(self.images)

    @property
    def has_precomputed(self) -> bool:
        return (
            self.precomputed is not None
            and bool(self.precomputed.tutor_descriptions)
            and bool(self.precomputed.feature_queries)
            and bool(self.precomputed.validator_answers)
        )

    def image_path(self, img: ManifestImage, manifest_path: Path) -> Path:
        """Resolve absolute path to an image file."""
        return manifest_path.parent / self.images_dir / img.filename

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkManifest":
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        images = [
            ManifestImage(
                image_id   = e["image_id"],
                filename   = e["filename"],
                true_class = e["true_class"],
                difficulty = e.get("difficulty", DIFFICULTY_MEDIUM),
                notes      = e.get("notes", ""),
                metadata   = e.get("metadata", {
                    k: e[k] for k in ("friction","material","roughness","lesion_id",
                                      "diagnosis","species_id")
                    if k in e
                }),
            )
            for e in data.get("images", [])
        ]

        precomputed = None
        if "precomputed" in data and data["precomputed"]:
            pc = data["precomputed"]
            queries = [
                FeatureQuery(
                    feature_id=q["feature_id"],
                    question=q["question"],
                    diagnostic_for=q["diagnostic_for"],
                    difficulty=q.get("difficulty", DIFFICULTY_MEDIUM),
                )
                for q in pc.get("feature_queries", [])
            ]
            precomputed = Precomputed(
                tutor_model        = pc.get("tutor_model", ""),
                validator_model    = pc.get("validator_model", ""),
                generated          = pc.get("generated", ""),
                tutor_descriptions = pc.get("tutor_descriptions", {}),
                feature_queries    = queries,
                validator_answers  = pc.get("validator_answers", {}),
                seed_rules         = pc.get("seed_rules"),
                seed_rule          = pc.get("seed_rule"),
            )

        return cls(
            benchmark_id   = data["benchmark_id"],
            schema_version = data.get("schema_version", "1.0"),
            version        = data.get("version", "1.0.0"),
            domain         = data.get("domain", ""),
            created        = data.get("created", ""),
            pair_id        = data["pair_id"],
            class_a        = data["class_a"],
            class_b        = data["class_b"],
            description    = data.get("description", ""),
            images         = images,
            precomputed    = precomputed,
            images_dir     = data.get("images_dir", "images/"),
        )


# ---------------------------------------------------------------------------
# Result report
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Probe result for one PUPIL model against one benchmark manifest.

    Fields that require specific probe steps may be None when results were
    derived from a pre-manifest DD session (import_dd_session.py) rather
    than a full 4-step probe run:
      - perception_score         (Step 3 — feature detection, PUPIL vs VALIDATOR GT)
      - vocabulary_overlap       (Step 2 — PUPIL free-description vs TUTOR vocabulary)
      - consistency_score        (Step 4b — repeated runs on same images)
      - feature_detection_by_difficulty / feature_profile  (Step 3 detail)

    When these are None the leaderboard shows "N/A".  The verdict is set to
    "partial" and the notes field explains what data source was used.
    """
    benchmark_id:            str
    benchmark_version:       str
    schema_version:          str
    submitted:               str       # ISO datetime
    pupil_model:             str
    tutor_model:             str
    validator_model:         str
    verdict:                 str       # "go" | "partial" | "no-go"
    # Core scores — None when not measured (pre-manifest DD session imports)
    perception_score:        Optional[float]
    vocabulary_overlap:      Optional[float]
    zero_shot_accuracy:      float
    rule_aided_accuracy:     float
    rule_comprehension_delta: float
    consistency_score:       Optional[float]
    feature_detection_by_difficulty: Optional[Dict[str, Optional[float]]]
    feature_profile:         Optional[Dict[str, float]]
    weak_points:             List[str]
    recommendations:         List[str]
    costs:                   Dict[str, dict]
    total_cost_usd:          float
    # Rule quality gate — VALIDATOR-based check that generated rules are discriminative
    # before attributing a low PUPIL delta to poor rule-following.
    rule_gate_accuracy:      Optional[float] = None   # VALIDATOR accuracy on held-out subset with rule
    rule_gate_passed:        Optional[bool]  = None   # True if gate_accuracy >= threshold
    # Optional detailed data
    per_image_zero_shot:     List[dict] = field(default_factory=list)
    per_image_rule_aided:    List[dict] = field(default_factory=list)
    notes:                   str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str | Path) -> "ProbeResult":
        with open(Path(path), encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
