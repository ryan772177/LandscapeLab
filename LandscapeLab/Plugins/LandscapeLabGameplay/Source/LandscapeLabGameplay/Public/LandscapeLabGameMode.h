// Copyright Ryan B. LandscapeLab.
//
// The game mode. PHASE2_PLAN.md unit 5 item 1: DefaultEngine.ini sets only
// GameDefaultMap -- there is no GlobalDefaultGameMode and no default pawn, so
// a cook today ships Epic's template world with Epic's default pawn.
//
// AGameModeBase rather than AGameMode: this is a confirmed single-player game
// (WORLD_VISION.md:178) and AGameMode's match-state machine is multiplayer
// machinery nothing here uses.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "LandscapeLabGameMode.generated.h"

UCLASS()
class LANDSCAPELABGAMEPLAY_API ALandscapeLabGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ALandscapeLabGameMode();
};
