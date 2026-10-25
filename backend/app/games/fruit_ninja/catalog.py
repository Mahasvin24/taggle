"""Private reference catalog. Never serialize these source labels to gameplay."""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = BACKEND_ROOT / "assets" / "fruit_ninja"
REFERENCE_VERSION = "fruit-shift-controls-v1"
CONTROL_GROUPS = {
    "fresh": {
        "apple": {"0017": [1], "0083": [1], "0149": [2, 5, 7, 8, 10, 14]},
        "banana": {"0283": [1, 2, 4, 5]},
        "grape": {
            "0417": list(range(1, 9)),
            "0483": [1, 2, 3, 4, 5, 7, 8, 10],
            "0549": [1, 2],
        },
        "guava": {"0617": [1], "0749": [1]},
        "jujube": {"0949": [1, 2, 8]},
        "orange": {"1083": [1]},
        "pomegranate": {"1349": [1]},
        "strawberry": {"1483": [1, 2, 4, 5, 6, 8, 9, 12, 14, 26, 47, 51, 56, 58, 67]},
    },
    "rotten": {
        "apple": {"1617": [2], "1683": [1]},
        "banana": {"1817": [1], "1883": [1]},
        "grape": {"2017": [9, 10, 12, 13], "2083": [2, 7], "2149": [2, 5]},
        "guava": {"2217": [1], "2349": [1]},
        "orange": {"2617": [1], "2749": [1]},
        "pomegranate": {"2817": [1], "2883": [1]},
        "strawberry": {
            "3017": [
                2,
                3,
                5,
                7,
                8,
                9,
                10,
                12,
                13,
                15,
                16,
                17,
                20,
                21,
                23,
                24,
                26,
                27,
                28,
                29,
            ],
            "3083": [1],
        },
    },
}
CONTROL_IDS = {
    f"{fruit}-{state}-{row}-fruit-{number:02d}"
    for state, fruits in CONTROL_GROUPS.items()
    for fruit, groups in fruits.items()
    for row, numbers in groups.items()
    for number in numbers
}
# All ten are existing frozen controls; no target labels are disclosed.
DEMONSTRATIONS = [
    ("strawberry-fresh-1483-fruit-01", "fresh", "Glossy skin and distinct seeds. Let it fly."),
    ("strawberry-fresh-1483-fruit-12", "fresh", "Bright red, with an intact surface. An easy keeper."),
    ("strawberry-fresh-1483-fruit-47", "fresh", "The pale area by the leaves is natural coloring."),
    ("strawberry-fresh-1483-fruit-08", "fresh", "A darker berry can still be healthy. Color alone is not decay."),
    ("strawberry-fresh-1483-fruit-51", "fresh", "Less glossy and a little uneven, but no broad sunken damage."),
    ("strawberry-rotten-3017-fruit-08", "rotten", "A large collapsed, tan patch. This one gets a slice."),
    ("strawberry-rotten-3017-fruit-17", "rotten", "Deep brown, sunken damage breaks up the red skin."),
    ("strawberry-rotten-3017-fruit-02", "rotten", "Look at the dull brown patch on the side, even though much is still red."),
    ("strawberry-rotten-3017-fruit-13", "rotten", "The yellow-brown area and wrinkled surface are the clues here."),
    ("strawberry-rotten-3017-fruit-20", "rotten", "A subtler one: shriveled, collapsed flesh rather than just a dark color."),
]


def wave_schedule(count: int = 32) -> list[tuple[int, float]]:
    """21 constant-cadence waves, alternating two fruit and one fruit."""
    result = []
    for wave in range(21):
        lanes = (0.23, 0.77) if wave % 2 == 0 else (0.5,)
        result.extend((800 + wave * 2800, lane) for lane in lanes)
    assert len(result) == count
    return result
