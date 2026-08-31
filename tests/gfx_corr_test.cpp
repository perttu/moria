// Assertions on Henrik Harmsen's GFX_CORR table.
//
// The point of this port is preservation, so the thing worth testing is that
// the mapping still says what the 1992 source said. These values come from
// amiga_corrlist.c; if the extractor or the table ever drifts, this fails.
#include <cstdio>
#include <cstdlib>

#include "amiga_tiles.hpp"
#include "amiga_tiles_table.generated.hpp"

namespace {

int g_failures = 0;

void expect_tile(const char *what, std::uint8_t code, int x, int y) {
    const moria::gfx::Tile tile = moria::gfx::tile_for(code);
    if (tile.x != x || tile.y != y) {
        std::printf("FAIL %-24s expected {%d,%d}, got {%d,%d}\n",
                    what, x, y, tile.x, tile.y);
        ++g_failures;
        return;
    }
    if (!moria::gfx::is_explicit(code)) {
        std::printf("FAIL %-24s matched, but is not marked as explicitly mapped\n",
                    what);
        ++g_failures;
        return;
    }
    std::printf("ok   %-24s {%d,%d}\n", what, x, y);
}

void expect(const char *what, bool condition) {
    if (condition) {
        std::printf("ok   %s\n", what);
    } else {
        std::printf("FAIL %s\n", what);
        ++g_failures;
    }
}

}  // namespace

int main() {
    expect_tile("player '@'", '@', 10, 2);
    expect_tile("floor '.'", '.', 20, 1);
    expect_tile("wall '#'", '#', 13, 2);
    expect_tile("bird 'B'", 'B', 2, 1);
    expect_tile("dragon 'D'", 'D', 2, 3);
    expect_tile("potion '!'", '!', 12, 4);
    expect_tile("edged weapon '|'", '|', 6, 6);
    expect_tile("polearm '/'", '/', 8, 6);

    // Henrik gave several creatures graphics beyond standard UMoria's ASCII
    // categories, using display codes above 127. Losing those would silently
    // flatten the artwork back to the plain symbol set.
    int extended = 0;
    for (int code = 128; code <= 255; ++code) {
        if (moria::gfx::is_explicit(static_cast<std::uint8_t>(code))) {
            ++extended;
        }
    }
    expect("all 128 extended display codes are mapped", extended == 128);

    // Every entry must land inside the 40x7 atlas, seeded ones included --
    // that is what stops hallucination from sampling outside the artwork.
    bool in_range = true;
    for (int code = 0; code <= 255; ++code) {
        const moria::gfx::Tile tile =
            moria::gfx::tile_for(static_cast<std::uint8_t>(code));
        if (tile.x >= 40 || tile.y >= 7) {
            std::printf("     code %d maps outside the atlas: {%d,%d}\n",
                        code, tile.x, tile.y);
            in_range = false;
        }
    }
    expect("every display code lands inside the 40x7 atlas", in_range);

    expect("explicit_count() agrees with the extracted table",
           moria::gfx::explicit_count() == 230);

    // The seeding parameters are as load-bearing as the mappings. If the
    // extractor ever failed to find them and fell back to something
    // harmless-looking, hallucination would draw from a different part of
    // the atlas and no rendered screen would look wrong enough to notice.
    expect("seed range for cx is randint(33)", moria::gfx::kSeedXRange == 33);
    expect("seed range for cy is randint(7)", moria::gfx::kSeedYRange == 7);
    expect("seed fixup is (cx > 13 && cx < 20) -> cx -= 6",
           moria::gfx::kSeedFixupLow == 13 && moria::gfx::kSeedFixupHigh == 20
               && moria::gfx::kSeedFixupSubtract == 6);

    // The fixup's observable consequence: no seeded entry may land in the
    // 14..19 column band. Explicit mappings are free to. Checking the
    // consequence rather than a literal tile keeps this independent of which
    // random engine the standard library provides.
    bool band_clear = true;
    for (std::uint32_t seed = 0; seed < 32; ++seed) {
        const std::array<moria::gfx::Tile, 256> table = moria::gfx::build_table(seed);
        for (int code = 0; code <= 255; ++code) {
            if (moria::gfx::is_explicit(static_cast<std::uint8_t>(code))) {
                continue;
            }
            const int x = table[code].x;
            if (x > moria::gfx::kSeedFixupLow && x < moria::gfx::kSeedFixupHigh) {
                std::printf("     seed %u, code %d seeded into the fixed-up "
                            "band at x=%d\n", seed, code, x);
                band_clear = false;
            }
        }
    }
    expect("seeded entries never land in the band the fixup clears", band_clear);

    if (g_failures != 0) {
        std::printf("\n%d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("\nall checks passed\n");
    return 0;
}
