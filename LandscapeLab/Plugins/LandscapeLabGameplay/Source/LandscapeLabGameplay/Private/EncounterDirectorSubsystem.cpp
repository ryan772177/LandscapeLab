// Copyright Ryan B. LandscapeLab.

#include "EncounterDirectorSubsystem.h"

#include "EncounterMarker.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "NavigationSystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogEncounterDirector, Log, All);

namespace
{
	FEncounterKey KeyOf(const AEncounterMarker* Marker)
	{
		FEncounterKey Key;
		if (Marker)
		{
			Key.PlanId = Marker->PlanId;
			Key.RowIndex = Marker->PlanRowIndex;
		}
		return Key;
	}
}

bool UEncounterDirectorSubsystem::DoesSupportWorldType(
	const EWorldType::Type WorldType) const
{
	// Game and PIE only. An editor world has no player to be near, and a
	// director ticking in the editor would act on the level being authored.
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UEncounterDirectorSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UEncounterDirectorSubsystem,
		STATGROUP_Tickables);
}

void UEncounterDirectorSubsystem::RefreshMarkers()
{
	Markers.Reset();
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	for (TActorIterator<AEncounterMarker> It(World); It; ++It)
	{
		Markers.Add(*It);
	}
	Stats.KnownMarkers = Markers.Num();
	++Stats.Rescans;
}

void UEncounterDirectorSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// ON A TIMER, NOT ON EMPTINESS. The first draft rescanned only when the
	// list was empty, which is wrong in both directions: a world with genuinely
	// zero markers rescanned every evaluation forever (a full TActorIterator
	// walk over 2,500+ external actors), and once ONE marker was found the list
	// never returned to empty -- stale weak pointers still count toward Num()
	// -- so markers streaming in later were never discovered at all. Markers
	// are spatially loaded BY DESIGN, so discovery cannot be single-shot.
	TimeSinceRescan += DeltaTime;
	if (TimeSinceRescan >= RescanIntervalSeconds)
	{
		TimeSinceRescan = 0.f;
		RefreshMarkers();
	}

	TimeSinceEvaluate += DeltaTime;
	if (TimeSinceEvaluate < EvaluateIntervalSeconds)
	{
		return;
	}
	TimeSinceEvaluate = 0.f;
	Evaluate();
}

void UEncounterDirectorSubsystem::Evaluate()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// THE HYSTERESIS INVARIANT, ASSERTED RATHER THAN ASSUMED. Warn ONCE -- a
	// per-tick log is its own defect -- and carry on with a corrected radius
	// rather than flipping every evaluation.
	float EffectiveDeactivate = DeactivateRadiusCm;
	if (DeactivateRadiusCm <= ActivateRadiusCm)
	{
		if (!bWarnedRadiiInverted)
		{
			bWarnedRadiiInverted = true;
			UE_LOG(LogEncounterDirector, Warning,
				TEXT("DeactivateRadiusCm (%.0f) must EXCEED ActivateRadiusCm "
					 "(%.0f) or a site flips every evaluation at the boundary. "
					 "Using %.0f until this is corrected."),
				DeactivateRadiusCm, ActivateRadiusCm, ActivateRadiusCm * 1.5f);
		}
		EffectiveDeactivate = ActivateRadiusCm * 1.5f;
	}

	// The streaming source is the player's pawn. No pawn is not an error -- it
	// is the state before possession -- and evaluating anyway would measure
	// distance from the world origin.
	const APlayerController* PC = World->GetFirstPlayerController();
	const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	const FVector Origin = Pawn->GetActorLocation();

	UNavigationSystemV1* Nav =
		FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);

	// Deactivate first, so freed slots are available to activations in the
	// SAME evaluation. Otherwise a player leaving one encounter and entering
	// another at the cap would wait a full interval for the swap.
	//
	// A site whose marker has streamed out stays ACTIVE deliberately: the
	// encounter is a plan row, not an actor, and its cell coming and going is
	// not the player leaving it. Only distance deactivates.
	TArray<FEncounterKey> ToDeactivate;
	TSet<FEncounterKey> SeenThisPass;
	int32 Loaded = 0;

	for (const TWeakObjectPtr<AEncounterMarker>& Weak : Markers)
	{
		const AEncounterMarker* Marker = Weak.Get();
		if (!Marker)
		{
			continue;
		}
		++Loaded;
		const FEncounterKey Key = KeyOf(Marker);
		SeenThisPass.Add(Key);
		if (!ActiveKeys.Contains(Key))
		{
			continue;
		}
		const float DistSq =
			FVector::DistSquared(Origin, Marker->GetActorLocation());
		if (DistSq > EffectiveDeactivate * EffectiveDeactivate)
		{
			ToDeactivate.Add(Key);
		}
	}
	for (const FEncounterKey& Key : ToDeactivate)
	{
		ActiveKeys.Remove(Key);
	}

	for (const TWeakObjectPtr<AEncounterMarker>& Weak : Markers)
	{
		const AEncounterMarker* Marker = Weak.Get();
		if (!Marker)
		{
			continue;
		}
		const FEncounterKey Key = KeyOf(Marker);
		if (ActiveKeys.Contains(Key))
		{
			continue;
		}

		const float DistSq =
			FVector::DistSquared(Origin, Marker->GetActorLocation());
		if (DistSq > ActivateRadiusCm * ActivateRadiusCm)
		{
			continue;
		}

		if (ActiveKeys.Num() >= MaxActiveEncounters)
		{
			// DISTINCT sites, not attempts -- a site inside the radius is
			// retried every evaluation and counting attempts would make any
			// gate asserting a magnitude read a time-dependent number.
			if (!RefusedAtCapKeys.Contains(Key))
			{
				RefusedAtCapKeys.Add(Key);
				++Stats.SitesRefusedAtCap;
			}
			continue;
		}

		// ** REFUSE WHEN THE SITE WILL NOT PROJECT. ** A chunk that has not
		// streamed cannot host anything that moves. Refusing is recoverable;
		// the next evaluation retries once the chunk arrives.
		bool bProjects = false;
		if (Nav)
		{
			FNavLocation Projected;
			const FVector Extent(NavProjectExtentCm, NavProjectExtentCm,
				NavProjectExtentCm);
			bProjects = Nav->ProjectPointToNavigation(
				Marker->GetActorLocation(), Projected, Extent);
		}
		// No navigation system at all is COULD NOT LOOK, not "the site is
		// fine", and bProjects stays false.
		if (!bProjects)
		{
			if (!RefusedNoNavKeys.Contains(Key))
			{
				RefusedNoNavKeys.Add(Key);
				++Stats.SitesRefusedNoNavmesh;
			}
			continue;
		}

		// A site that has since projected is no longer a standing refusal.
		RefusedNoNavKeys.Remove(Key);
		ActiveKeys.Add(Key);
	}

	Stats.KnownMarkers = Loaded;
	Stats.ActiveEncounters = ActiveKeys.Num();
}

bool UEncounterDirectorSubsystem::IsRowActive(const FString& InPlanId,
	int32 RowIndex) const
{
	FEncounterKey Key;
	Key.PlanId = InPlanId;
	Key.RowIndex = RowIndex;
	return ActiveKeys.Contains(Key);
}

FEncounterDirectorStats UEncounterDirectorSubsystem::GetStats() const
{
	return Stats;
}
