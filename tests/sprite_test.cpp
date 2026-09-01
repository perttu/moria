// Assertions on Henrik Harmsen's extended display codes.
//
// Standard Umoria draws every centipede as 'c' and every townsperson as 'p'.
// Henrik gave 96 creatures and 139 objects their own graphics using codes
// outside the printable range. Losing any of them is invisible in a
// screenshot -- the game still draws *something* -- so the mapping is checked
// by name here.
#include <cstdio>

#include "amiga_sprites.hpp"
#include "amiga_tiles.hpp"
#include "headers.h"

namespace {

int g_failures = 0;

void expectCode(const char *what, unsigned char got, unsigned char want) {
    if (got == want) {
        std::printf("ok   %-42s %3d\n", what, want);
        return;
    }
    std::printf("FAIL %-42s expected %d, got %d\n", what, want, got);
    ++g_failures;
}

void expectTrue(const char *what, bool condition) {
    if (condition) {
        std::printf("ok   %s\n", what);
    } else {
        std::printf("FAIL %s\n", what);
        ++g_failures;
    }
}

}  // namespace

int main() {
    // Counts, so a rename upstream cannot quietly drop a graphic.
    expectTrue("96 creatures carry a custom display code",
               moria::engine::creatureCodeCount() == 96);
    expectTrue("139 objects carry a custom display code",
               moria::engine::objectCodeCount() == 139);

    // Values straight out of Henrik's 1.1 tables.
    expectCode("Filthy Street Urchin",
               moria::engine::creatureCodeByName("Filthy Street Urchin"), 133);
    expectCode("Singing, Happy Drunk",
               moria::engine::creatureCodeByName("Singing, Happy Drunk"), 138);
    expectCode("Ancient Red Dragon",
               moria::engine::creatureCodeByName("Ancient Red Dragon"), 238);
    expectCode("Ancient Multi-Hued Dragon",
               moria::engine::creatureCodeByName("Ancient Multi-Hued Dragon"), 239);
    expectCode("Giant White Centipede",
               moria::engine::creatureCodeByName("Giant White Centipede"), 247);
    expectCode("Large White Snake",
               moria::engine::creatureCodeByName("Large White Snake"), 252);
    // Not every custom code is above 127; the low ones are just as real.
    expectCode("White Icky-Thing",
               moria::engine::creatureCodeByName("White Icky-Thing"), 10);

    // A creature Henrik left on its plain letter must stay on it.
    expectCode("Giant White Mouse, which he did not redraw",
               moria::engine::creatureCodeByName("Giant White Mouse"), 0);
    expectCode("a name that does not exist",
               moria::engine::creatureCodeByName("Space Marine"), 0);

    // Objects, including the five Umoria renamed between 5.4 and 5.7.15.
    // Without the rename table these would silently lose their graphics.
    expectTrue("& Lead-Filled Mace, renamed from '& Mace (Lead-filled)'",
               moria::engine::objectCodeByName("& Lead-Filled Mace") != 0);
    expectTrue("[Magick I], renamed from '[Magik I]'",
               moria::engine::objectCodeByName("[Magick I]") != 0);
    expectTrue("[Magick II], renamed from '[Magik II]'",
               moria::engine::objectCodeByName("[Magick II]") != 0);
    expectTrue("[Beginners-Magick], renamed from '[Beginners-Magik]'",
               moria::engine::objectCodeByName("[Beginners-Magick]") != 0);
    expectTrue("[Exorcisms and Dispellings], renamed from the singular",
               moria::engine::objectCodeByName("[Exorcisms and Dispellings]") != 0);
    expectTrue("& Cat-o'-Nine-Tails, matched past its punctuation",
               moria::engine::objectCodeByName("& Cat-o'-Nine-Tails") != 0);

    // Every recovered code must have a tile of its own in GFX_CORR. A code
    // without one would draw whatever the hallucination seeding left there,
    // which is a plausible-looking graphic and therefore easy to miss.
    int checked = 0;
    bool all_mapped = true;
    for (int i = 0; i < MON_MAX_CREATURES; ++i) {
        const unsigned char code =
            moria::engine::creatureCodeByName(creatures_list[i].name);
        if (code == 0) {
            continue;
        }
        ++checked;
        if (!moria::gfx::is_explicit(code)) {
            std::printf("     %s uses code %d, which GFX_CORR does not map\n",
                        creatures_list[i].name, code);
            all_mapped = false;
        }
    }
    expectTrue("every creature code has an explicit GFX_CORR tile", all_mapped);
    expectTrue("and every one was found in Umoria's creature list",
               checked == moria::engine::creatureCodeCount());
    std::printf("     %d creatures resolved against Umoria's own table\n", checked);

    if (g_failures != 0) {
        std::printf("\n%d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("\nHenrik's extended graphics are all present\n");
    return 0;
}
