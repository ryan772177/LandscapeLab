// Copyright Ryan B. LandscapeLab.

#include "EncounterMarker.h"

#include "Components/SceneComponent.h"

AEncounterMarker::AEncounterMarker()
{
	// NO TICK. 317 markers that tick is 317 ticks for data that never changes.
	PrimaryActorTick.bCanEverTick = false;
	PrimaryActorTick.bStartWithTickEnabled = false;

	// A bare SceneComponent so the actor has a transform and nothing else.
	// Not a UStaticMeshComponent with no mesh: that still registers a primitive
	// with the renderer and the physics scene, which is exactly the cost this
	// class exists to avoid.
	USceneComponent* Root =
		CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	// SPATIALLY LOADED, which is the whole point: markers stream with the
	// region so 317 of them cost nothing until the player is near one. The
	// PAWN a marker will eventually spawn must be the opposite -- see the
	// header. This is also AActor's default; it is written explicitly because
	// the streaming behaviour is load-bearing here and a silent default is a
	// decision nobody made.
	bIsSpatiallyLoaded = true;

	// Never relevant to the renderer or to gameplay collision.
	SetActorEnableCollision(false);
	SetHidden(true);

	// ⛔ NO BILLBOARD, AND SAYING SO RATHER THAN IMPLYING ONE.
	// The first draft carried a comment promising "the billboard costs nothing
	// in a cooked build" beside a `bIsEditorOnlyActor = false` that wrote the
	// existing default under a WITH_EDITORONLY_DATA guard the member does not
	// need (Actor.h:561-563 -- it exists in all builds). Three defects in five
	// lines, net effect nothing, and an audit caught it before compilation.
	//
	// So: A MARKER IS INVISIBLE IN THE VIEWPORT. That is deliberate -- 317
	// billboard components is 317 primitives for data the player must never
	// see. To look at encounter sites, draw them: the plan is on disk at
	// encounters/<region>_verified.json and a debug-draw pass over it costs
	// nothing when it is not running.
}
