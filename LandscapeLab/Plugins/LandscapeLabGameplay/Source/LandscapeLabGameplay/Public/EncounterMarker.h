// Copyright Ryan B. LandscapeLab.
//
// PHASE2_PLAN.md unit 10. A DATA-ONLY encounter site: no mesh, no tick, no
// collision. One OFPA package each, spatially loaded, exactly like the foliage
// plans.
//
// WHY THE MARKER AND THE ENEMY ARE DIFFERENT ACTORS.
// A World Partition streamed actor is DESTROYED on cell unload and recreated
// fresh -- health, aggro and patrol progress gone. At a 256 m streaming range
// with a 3x mount that boundary is crossed constantly, so a streamed enemy
// would reset every time the player rides past. The MARKER streams (it is
// static data and cheap to recreate); the PAWN it spawns does not, and is owned
// by a director subsystem with spawn/despawn hysteresis.
//
// WHY IT CARRIES NO MESH AND NO TICK.
// The region's plan holds 317 of these. A marker that ticks is 317 ticks for
// data that never changes, and a marker with a mesh is 317 draw calls for
// something the player must never see. Anything visible at an encounter site
// belongs to the pawn, which exists only while the encounter is active.
//
// EVERY FIELD HERE COMES FROM THE PLAN, so a placed marker can be compared to
// encounters/<region>_verified.json field by field. A marker that cannot be
// traced back to a plan row is an actor nobody can re-derive.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "EncounterMarker.generated.h"

UCLASS(BlueprintType)
class LANDSCAPELABGAMEPLAY_API AEncounterMarker : public AActor
{
	GENERATED_BODY()

public:
	AEncounterMarker();

	/** Archetype key from recipes/encounters.json -- a KEY, never a class. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	FName Archetype;

	/** Inclusive party size chosen by the planner for THIS site. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	int32 PartySize = 1;

	/**
	 * Distance at which this encounter notices the player, centimetres.
	 * Carried from the plan rather than read from a class default: the
	 * planner's SEPARATION between encounters is computed from aggro+leash, so
	 * a marker whose radius disagrees with the plan silently invalidates the
	 * spacing the plan was gated on.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	float AggroRadiusCm = 0.f;

	/** Distance beyond which spawned pawns give up and return, centimetres. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	float LeashRadiusCm = 0.f;

	/** Ground elevation the planner recorded, metres. Diagnostic. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	float PlannedElevationM = 0.f;

	/**
	 * Index of this row in the plan that produced it, and the plan's own id.
	 * A marker that cannot name its source row cannot be diffed against the
	 * plan, and this project's rule is that a derived record verifies against
	 * ground truth.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	int32 PlanRowIndex = -1;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Encounter")
	FString PlanId;
};
