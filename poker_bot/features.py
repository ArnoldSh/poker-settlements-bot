from __future__ import annotations

from dataclasses import dataclass


# Keep this default as the complete list of guarded features.
# New guarded commands must be added here so they stay enabled by default.
DEFAULT_ENABLED_FEATURES = "revanche,savegroup,groups,analyze,history,export_csv,sub_refund"


FEATURE_ALIASES: dict[str, tuple[str, ...]] = {}


def parse_feature_list(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()

    features: set[str] = set()
    for raw_item in value.split(","):
        item = raw_item.strip().lower().replace("-", "_")
        if not item:
            continue
        for feature in FEATURE_ALIASES.get(item, (item.replace(" ", "_"),)):
            features.add(feature)
    return frozenset(features)


@dataclass(frozen=True)
class FeatureFlags:
    enabled_features: frozenset[str]

    def is_enabled(self, feature: str) -> bool:
        return feature in self.enabled_features
