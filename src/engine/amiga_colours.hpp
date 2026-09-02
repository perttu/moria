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
// is organised to avoid. So the colour is decided here instead.
//
// The stat block is read from the game's own state, which is exact. The
// message line cannot be: Umoria prints a message *before* it applies the
// consequence -- the attack description before the damage, "You feel weaker."
// before the stat drops, "You have picked the lock." before the experience is
// awarded -- so at the moment a message is written, nothing has happened yet.
// Messages are therefore classified from their text, using phrases taken from
// Umoria's source. That is an approximation of Henrik's per-call-site choice,
// and phrases it does not know are drawn in white.
#pragma once

#include "ui.hpp"

namespace moria::engine::colours {

// Colour for a run of text about to be written at this position.
ui::Color forText(int row, int col, const char *text);

}  // namespace moria::engine::colours
