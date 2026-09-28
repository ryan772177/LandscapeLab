// Copyright Ryan B. LandscapeLab.

#include "LandscapeLabGameMode.h"

#include "LandscapeLabCharacter.h"

ALandscapeLabGameMode::ALandscapeLabGameMode()
{
	// Set in C++ rather than in an ini, so that "which pawn does this game
	// spawn" is answerable by reading the class instead of by reading a
	// config file -- non-negotiable 17: a config records what was OVERRIDDEN,
	// never what is in effect.
	DefaultPawnClass = ALandscapeLabCharacter::StaticClass();
}
