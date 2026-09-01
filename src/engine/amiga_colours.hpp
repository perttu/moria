// Henrik Harmsen's colour scheme, decided at the presentation layer.
//
// Amiga.doc describes the scheme precisely:
//
//   White       normal info
//   Red         danger -- you are hurt, or something really bad happens
//   Yellow      warning -- trouble, or you failed to do something
//   Green       you hit a monster, or succeeded at something
//   Light blue  you killed a monster
//   Dark red    real danger -- one of your stats has decreased
//   Blue        one of your stats has increased
//
// and for the stat block:
//
//   "When some status has decreased, it will be displayed in yellow. When
//    hitpoints or mana is between 0-25% it will be red, 25%-75% in yellow,
//    75%-100% in light green and 100% in white."
//
// Update.doc adds that 'Hungry' is yellow and 'Weak' is red, and that the
// "-more-" prompt is deliberately *not* coloured, so it cannot give away a
// kill before the message arrives.
//
// Henrik implemented this by passing a colour from each engine call site.
// This port does not: modifying gameplay source is the one thing the project
// is organised to avoid. So the colour is decided here instead, from the
// screen position and -- where the documentation is precise about it -- from
// the game's own state.
#pragma once

#include "ui.hpp"

namespace moria::engine::colours {

// Colour for a run of text about to be written at this position.
ui::Color forText(int row, int col, const char *text);

}  // namespace moria::engine::colours
