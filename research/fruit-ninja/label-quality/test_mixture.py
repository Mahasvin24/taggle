"""Verify the 70/30 comparison changes label origin without changing data coverage."""

import json
from pathlib import Path
import unittest
import numpy as np

from run_experiment import aggregate_votes
from run_mixture import select_mix, MIX_SEEDS


class MixtureTests(unittest.TestCase):
    def test_selection_is_deterministic_unique_and_rounded_to_thirty_percent(self):
        train = [
            {"id": str(i), "source_label": "fresh" if i % 2 else "rotten"}
            for i in range(183)
        ]
        game = {str(i): int(i % 2) for i in range(68)}
        y, selected, changed = select_mix(train, game, MIX_SEEDS[0])
        other, selected_again, _ = select_mix(list(reversed(train)), game, MIX_SEEDS[0])
        self.assertEqual(len(selected), 55)
        self.assertEqual(selected, selected_again)
        self.assertEqual(len(y), 183)
        self.assertEqual(changed, 55)
        self.assertEqual(
            len(selected | {a["id"] for a in train if a["id"] not in selected}), 183
        )
        for a, label in zip(train, y):
            self.assertEqual(
                label,
                (
                    game[a["id"]]
                    if a["id"] in selected
                    else int(a["source_label"] == "rotten")
                ),
            )
        reverse_by_id = dict(zip([a["id"] for a in reversed(train)], other))
        np.testing.assert_array_equal(y, [reverse_by_id[a["id"]] for a in train])

    def test_same_value_labels_still_count_as_gameplay_origin(self):
        train = [{"id": str(i), "source_label": "fresh"} for i in range(10)]
        y, selected, changed = select_mix(
            train, {str(i): 0 for i in range(10)}, MIX_SEEDS[0]
        )
        self.assertEqual(len(selected), 3)
        self.assertEqual(changed, 0)
        self.assertEqual(y.sum(), 0)

    def test_not_enough_game_labels_fails_instead_of_repeating_images(self):
        train = [{"id": str(i), "source_label": "fresh"} for i in range(10)]
        with self.assertRaises(ValueError):
            select_mix(train, {"0": 0}, MIX_SEEDS[0])

    def test_saved_comparison_excludes_photo_in_both_arms_and_respects_all_ratios(self):
        root = Path(__file__).parent / "results_mix"
        snapshot = json.loads((root / "snapshot.json").read_text())
        assets = {a["id"]: a for a in snapshot["assets"]}
        game, ties, _ = aggregate_votes(snapshot["eligible_target_votes"])
        tested = []
        for fold in json.loads((root / "folds.json").read_text()):
            held = fold["held_out_photo_sha256"]
            ids = fold["training_asset_ids"]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(
                set(ids),
                {
                    key
                    for key, a in assets.items()
                    if a["metadata"]["source_photo_sha256"] != held
                },
            )
            tested.extend(fold["test_asset_ids"])
            self.assertFalse(set(ids) & set(fold["test_asset_ids"]))
            for mixture in fold["mixtures"]:
                selected = set(mixture["gameplay_asset_ids"])
                self.assertEqual(len(selected), int(np.floor(0.3 * len(ids) + 0.5)))
                self.assertLessEqual(selected, set(ids) & set(game))
                self.assertFalse(selected & set(ties))
                self.assertEqual(
                    mixture["normal_rows"] + mixture["gameplay_rows"], len(ids)
                )
                self.assertLessEqual(
                    abs(mixture["gameplay_ratio"] - 0.3), 0.5 / len(ids) + 1e-12
                )
                labels = np.array(
                    [
                        (
                            game[key]
                            if key in selected
                            else int(assets[key]["source_label"] == "rotten")
                        )
                        for key in ids
                    ]
                )
                expected = sum(
                    int(label) != int(assets[key]["source_label"] == "rotten")
                    for key, label in zip(ids, labels)
                )
                self.assertEqual(expected, mixture["changed_labels"])
        self.assertCountEqual(
            tested, [key for key, a in assets.items() if a["role"] == "control"]
        )


if __name__ == "__main__":
    unittest.main()
