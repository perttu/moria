#include "amiga_sprites.hpp"

#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

#include "amiga_codes.generated.hpp"
#include "headers.h"

namespace moria::engine {
namespace {

using Lookup = std::unordered_map<std::string, unsigned char>;

const Lookup &creatureLookup() {
    static const Lookup lookup = [] {
        Lookup map;
        for (const auto &entry : gfx::kCreatureCodes) {
            map.emplace(entry.name, entry.code);
        }
        return map;
    }();
    return lookup;
}

const Lookup &objectLookup() {
    static const Lookup lookup = [] {
        Lookup map;
        for (const auto &entry : gfx::kObjectCodes) {
            map.emplace(entry.name, entry.code);
        }
        return map;
    }();
    return lookup;
}

unsigned char lookUp(const Lookup &lookup, const char *name) {
    if (name == nullptr) {
        return 0;
    }
    const auto found = lookup.find(name);
    return (found == lookup.end()) ? 0 : found->second;
}

// Resolved once per creature type rather than per drawn cell.
const std::vector<unsigned char> &creatureCodes() {
    static const std::vector<unsigned char> codes = [] {
        std::vector<unsigned char> table(MON_MAX_CREATURES, 0);
        for (int i = 0; i < MON_MAX_CREATURES; ++i) {
            table[i] = lookUp(creatureLookup(), creatures_list[i].name);
        }
        return table;
    }();
    return codes;
}

bool insideDungeon(int y, int x) {
    return y >= 0 && x >= 0 && y < dg.height && x < dg.width;
}

}  // namespace

unsigned char displayCodeFor(unsigned char symbol, int dungeon_y, int dungeon_x) {
    if (!insideDungeon(dungeon_y, dungeon_x)) {
        return symbol;
    }
    const Tile_t &tile = dg.floor[dungeon_y][dungeon_x];

    // A creature stands in front of whatever it is standing on.
    if (tile.creature_id > 1) {
        const Monster_t &monster = monsters[tile.creature_id];
        const Creature_t &creature = creatures_list[monster.creature_id];
        // Only substitute for the creature's own symbol. Anything else drawn
        // on this cell -- a remembered object, a spell effect -- is not it.
        if (symbol == creature.sprite) {
            const unsigned char code = creatureCodes()[monster.creature_id];
            if (code != 0) {
                return code;
            }
        }
    }

    if (tile.treasure_id != 0) {
        const Inventory_t &item = game.treasure.list[tile.treasure_id];
        if (symbol == item.sprite && item.id < MAX_OBJECTS_IN_GAME) {
            const unsigned char code =
                lookUp(objectLookup(), game_objects[item.id].name);
            if (code != 0) {
                return code;
            }
        }
    }

    return symbol;
}

int creatureCodeCount() {
    return gfx::kCreatureCodeCount;
}

int objectCodeCount() {
    return gfx::kObjectCodeCount;
}

unsigned char creatureCodeByName(const char *name) {
    return lookUp(creatureLookup(), name);
}

unsigned char objectCodeByName(const char *name) {
    return lookUp(objectLookup(), name);
}

}  // namespace moria::engine
