#include "amiga_tiles.hpp"

#include <bitset>
#include <random>

#include "amiga_tiles_table.generated.hpp"

namespace moria::gfx {
namespace {

std::bitset<256> g_explicit;

std::array<Tile, 256> build(std::uint32_t seed) {
    std::array<Tile, 256> table{};

    // init_GFX_CORR() opens by scattering every entry across the atlas:
    //
    //     cx = randint(33) - 1;
    //     cy = randint(7) - 1;
    //     if ((cx < 20) && (cx > 13)) cx -= 6;
    //
    // randint(N) returns 1..N, so cx lands in 0..32 and cy in 0..6, and the
    // fixup steps the 14..19 band down out of a region of the atlas Henrik
    // did not want turning up at random.
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> dx(0, kSeedXRange - 1);
    std::uniform_int_distribution<int> dy(0, kSeedYRange - 1);

    for (auto &entry : table) {
        int cx = dx(rng);
        int cy = dy(rng);
        if (cx < kSeedFixupHigh && cx > kSeedFixupLow) {
            cx -= kSeedFixupSubtract;
        }
        entry = {static_cast<std::uint8_t>(cx), static_cast<std::uint8_t>(cy)};
    }

    for (const auto &e : kGfxCorr) {
        table[e.code] = {e.x, e.y};
        g_explicit.set(e.code);
    }
    return table;
}

}  // namespace

const std::array<Tile, 256> &tiles(std::uint32_t seed) {
    static std::uint32_t built_seed = seed;
    static std::array<Tile, 256> table = build(seed);
    if (seed != built_seed) {
        built_seed = seed;
        table = build(seed);
    }
    return table;
}

Tile tile_for(std::uint8_t display_code) {
    return tiles()[display_code];
}

bool is_explicit(std::uint8_t display_code) {
    (void)tiles();  // ensure the table, and therefore the flags, exist
    return g_explicit.test(display_code);
}

int explicit_count() {
    return kGfxCorrCount;
}

}  // namespace moria::gfx
