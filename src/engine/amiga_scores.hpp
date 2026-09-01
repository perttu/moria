// Reporting a finished game, so a history of play can be kept.
//
// Umoria writes its high scores into a binary file with a running-XOR cipher
// and a layout that only its own reader knows. Rather than reverse-engineer
// that -- which is fragile, and which I got wrong twice trying -- the score is
// reported here at the moment the game builds it, with the fields already in
// hand.
//
// In the browser it is POSTed to the server the page came from. Natively it
// is appended to a JSON-lines file beside the save. Neither affects Umoria's
// own scores.dat, which is still written exactly as before.
#pragma once

namespace moria::engine {

// Called from recordNewHighScore() once the entry is filled in. Takes plain
// values so nothing above this header needs Umoria's types.
void reportScore(int points, int level, int depth, int deepest_depth,
                 int max_hp, int current_hp, char gender,
                 const char *race, const char *character_class,
                 const char *name, const char *died_from);

}  // namespace moria::engine
