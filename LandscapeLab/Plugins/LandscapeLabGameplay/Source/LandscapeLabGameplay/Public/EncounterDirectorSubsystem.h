// Copyright Ryan B. LandscapeLab.
//
// PHASE2_PLAN.md unit 10, FIRST HALF: encounter marker LIFECYCLE.
//
// ⛔ WHAT THIS DOES AND DOES NOT DO -- read before trusting the class name.
// It tracks which encounter SITES are near the player and decides when each
// becomes ACTIVE or INACTIVE, with hysteresis. **It spawns no pawns and owns
// none.** There is no enemy pawn class yet -- that is unit 12 -- and a header
// promising spawning that the code does not contain is exactly the defect
// non-negotiable 25 exists to prevent. The first draft of this file made that
// claim and an audit caught it before compilation.
//
// When unit 12 lands, the pawn goes here: spawned at bIsSpatiallyLoaded=false
// so it OUTLIVES its marker's cell. A World Partition streamed actor is
// DESTROYED on cell unload, so a streamed enemy would reset its health, aggro
// and patrol progress every time the player rides past at 3x mount speed.
//
// THE HYSTERESIS, AND WHERE ITS SHAPE COMES FROM.
// ActivateRadius < DeactivateRadius, the same asymmetry
// UNavigationInvokerComponent uses (NavigationInvokerComponent.h:22-28). With a
// single radius a player sitting on the boundary flips the same encounter every
// evaluation; the gap is what makes the boundary stable under jitter.
//
// ⛔ IDENTITY IS (PlanId, PlanRowIndex), NOT THE ACTOR POINTER.
// Markers are spatially loaded, so one streamed out and back is a DIFFERENT
// UObject with a different weak-pointer hash. Keying active state on the
// pointer loses the encounter's identity across exactly the event this design
// exists to survive, and leaks a stale entry every time. The plan row is the
// durable key, and it is what the marker itself carries for traceability.
//
// ** ACTIVATION REFUSES WHEN NAVMESH PROJECTION FAILS. ** A site whose chunk
// has not streamed cannot host anything that moves; activating it anyway would
// later spawn a pawn that stands still, which reads as an AI bug and is a
// streaming bug. Refusing is recoverable -- the next evaluation retries.
//
// WHY THE NUMBERS ARE CONFIG AND NOT C++ DEFAULTS.
// Pipeline rule 2: every scene parameter comes from recipe JSON. Same route the
// character uses -- recipes/encounters.json is the single declaration, a script
// projects it into DefaultGame.ini, this class reads that config at class load.
// MaxActiveEncounters in particular is an encounter-design ruling and belongs
// beside the density curve, not in a header.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EncounterDirectorSubsystem.generated.h"

class AEncounterMarker;

/** Durable identity of an encounter site: the plan row that produced it. */
USTRUCT()
struct FEncounterKey
{
	GENERATED_BODY()

	UPROPERTY()
	FString PlanId;

	UPROPERTY()
	int32 RowIndex = -1;

	bool operator==(const FEncounterKey& Other) const
	{
		return RowIndex == Other.RowIndex && PlanId == Other.PlanId;
	}
};

FORCEINLINE uint32 GetTypeHash(const FEncounterKey& Key)
{
	return HashCombine(GetTypeHash(Key.PlanId), ::GetTypeHash(Key.RowIndex));
}

USTRUCT(BlueprintType)
struct FEncounterDirectorStats
{
	GENERATED_BODY()

	/** Markers currently loaded and known to the director. */
	UPROPERTY(BlueprintReadOnly, Category = "Encounter")
	int32 KnownMarkers = 0;

	/** Encounter sites currently ACTIVE. */
	UPROPERTY(BlueprintReadOnly, Category = "Encounter")
	int32 ActiveEncounters = 0;

	/**
	 * DISTINCT sites refused because they would not project onto the navmesh.
	 * Distinct, not attempts: a site inside the radius but off-navmesh is
	 * retried every evaluation, and counting attempts would make any gate
	 * asserting a magnitude read a time-dependent number.
	 */
	UPROPERTY(BlueprintReadOnly, Category = "Encounter")
	int32 SitesRefusedNoNavmesh = 0;

	/** DISTINCT sites that hit the simultaneous-encounter cap. */
	UPROPERTY(BlueprintReadOnly, Category = "Encounter")
	int32 SitesRefusedAtCap = 0;

	/** Full marker rescans performed. Diagnostic for streaming churn. */
	UPROPERTY(BlueprintReadOnly, Category = "Encounter")
	int32 Rescans = 0;
};

UCLASS(config = Game, defaultconfig)
class LANDSCAPELABGAMEPLAY_API UEncounterDirectorSubsystem
	: public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	// UWorldSubsystem
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType)
		const override;

	// FTickableGameObject
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	/** Radius at which an encounter site becomes ACTIVE, centimetres. */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	float ActivateRadiusCm = 12000.f;

	/**
	 * Radius at which an active site is deactivated, centimetres.
	 * MUST exceed ActivateRadiusCm. Asserted at runtime rather than trusted:
	 * a config edit that inverts them produces a flip every evaluation, which
	 * presents as a performance problem and is a settings problem.
	 */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	float DeactivateRadiusCm = 20000.f;

	/** Ceiling on simultaneously active sites. An encounter-design ruling. */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	int32 MaxActiveEncounters = 6;

	/** Seconds between evaluations. Every frame is wasted for this. */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	float EvaluateIntervalSeconds = 0.5f;

	/**
	 * Seconds between full marker rescans. Markers stream in and out, so
	 * discovery cannot be single-shot -- and it cannot key off "the list is
	 * empty" either, because a list holding stale entries is never empty.
	 */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	float RescanIntervalSeconds = 5.f;

	/**
	 * Navmesh projection extent, centimetres. 500 is CALIBRATED, not chosen:
	 * a large query extent does not merely widen the search, it CHANGES the
	 * answer -- at 120 m the town plaza "projected" 116.7 m away, at 500 cm it
	 * projects at 0.0 cm lateral.
	 */
	UPROPERTY(config, BlueprintReadWrite, Category = "Encounter")
	float NavProjectExtentCm = 500.f;

	/** Read-only counters, for a gate to assert against. */
	UFUNCTION(BlueprintCallable, Category = "Encounter")
	FEncounterDirectorStats GetStats() const;

	/** Re-scan the world for markers. Cheap; also runs on a timer. */
	UFUNCTION(BlueprintCallable, Category = "Encounter")
	void RefreshMarkers();

	/** Is this plan row currently active? For gates and for unit 12. */
	UFUNCTION(BlueprintCallable, Category = "Encounter")
	bool IsRowActive(const FString& InPlanId, int32 RowIndex) const;

private:
	void Evaluate();

	/** Loaded markers, rebuilt on a timer. Weak: their cells stream out. */
	TArray<TWeakObjectPtr<AEncounterMarker>> Markers;

	/** ACTIVE sites, keyed by plan row so identity survives a cell reload. */
	TSet<FEncounterKey> ActiveKeys;

	/** Sites already counted as refused, so counters stay distinct. */
	TSet<FEncounterKey> RefusedNoNavKeys;
	TSet<FEncounterKey> RefusedAtCapKeys;

	FEncounterDirectorStats Stats;
	float TimeSinceEvaluate = 0.f;
	float TimeSinceRescan = 0.f;
	bool bWarnedRadiiInverted = false;
};
