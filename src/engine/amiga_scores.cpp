#include "amiga_scores.hpp"

#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif

namespace moria::engine {
namespace {

// Minimal JSON string escaping: names and death messages are player- and
// monster-supplied, and a stray quote would produce a document the server
// cannot read.
std::string quote(const char *text) {
    std::string out = "\"";
    for (const char *p = (text != nullptr) ? text : ""; *p != '\0'; ++p) {
        switch (*p) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(*p) < 0x20) {
                    char escape[8];
                    std::snprintf(escape, sizeof(escape), "\\u%04x", *p);
                    out += escape;
                } else {
                    out += *p;
                }
        }
    }
    return out + "\"";
}

std::string buildJson(int points, int level, int depth, int deepest_depth,
                      int max_hp, int current_hp, char gender,
                      const char *race, const char *character_class,
                      const char *name, const char *died_from) {
    const char gender_text[2] = {gender, '\0'};
    char numbers[256];
    std::snprintf(numbers, sizeof(numbers),
                  "\"points\":%d,\"level\":%d,\"depth\":%d,"
                  "\"deepest_depth\":%d,\"max_hp\":%d,\"current_hp\":%d,"
                  "\"finished\":%lld,",
                  points, level, depth, deepest_depth, max_hp, current_hp,
                  static_cast<long long>(std::time(nullptr)));

    return std::string("{") + numbers +
           "\"gender\":" + quote(gender_text) + "," +
           "\"race\":" + quote(race) + "," +
           "\"class\":" + quote(character_class) + "," +
           "\"name\":" + quote(name) + "," +
           "\"died_from\":" + quote(died_from) + "}";
}

}  // namespace

void reportScore(int points, int level, int depth, int deepest_depth,
                 int max_hp, int current_hp, char gender,
                 const char *race, const char *character_class,
                 const char *name, const char *died_from) {
    const std::string json = buildJson(points, level, depth, deepest_depth,
                                       max_hp, current_hp, gender, race,
                                       character_class, name, died_from);

#ifdef __EMSCRIPTEN__
    // Posted to whichever server served the page, so nothing has to be
    // configured. A failure is logged and ignored: losing a score entry must
    // never interfere with finishing a game.
    EM_ASM({
        var body = UTF8ToString($0);
        fetch('scores', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: body,
            keepalive: true
        }).catch(function (error) {
            console.error('moria: could not record the score:', error);
        });
    }, json.c_str());
#else
    // Natively, a JSON-lines file next to the binary. Appending means a
    // crash mid-write cannot corrupt earlier entries.
    if (FILE *file = fopen("scores.jsonl", "a")) {
        std::fprintf(file, "%s\n", json.c_str());
        std::fclose(file);
    }
#endif
}

}  // namespace moria::engine
