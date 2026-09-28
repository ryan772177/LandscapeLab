// Copyright Ryan B. LandscapeLab.

#include "LandscapeLabTools.h"

// --- MetaHuman DNA (2026-08-17). Every one of these was opened, not
// remembered; the header trail is in LandscapeLabTools.h.
#include "Commands/DNACalibSetNeutralJointTranslationsCommand.h"
#include "Commands/DNACalibSetVertexPositionsCommand.h"
#include "Commands/DNACalibVectorOperation.h"
#include "DNACalibDNAReader.h"
#include "DNACommon.h"
#include "DNAReader.h"
#include "DNAToSkelMeshMap.h"
#include "DNAUtils.h"
#include "Engine/SkeletalMesh.h"
#include "SkelMeshDNAUtils.h"

#include "Editor.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Landscape.h"
#include "LandscapeEditTypes.h"
#include "LandscapeImportHelper.h"
#include "LandscapeInfo.h"
#include "LandscapeProxy.h"
#include "LandscapeSubsystem.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "GroomAsset.h"
#include "GroomAsset.h"
#include "GroomAsset.h"
#include "GroomBindingAsset.h"
#include "HairStrandsCore.h"
#include "GroomBindingCompiler.h"
#include "GroomRBFDeformer.h"
#include "GroomRBFDeformer.h"
#include "GroomRBFDeformer.h"
#include "Materials/MaterialInterface.h"
#include "UObject/SavePackage.h"
#include "Misc/Paths.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionEditorLoaderAdapter.h"

DEFINE_LOG_CATEGORY_STATIC(LogLandscapeLab, Log, All);

namespace
{
	/**
	 * The engine's legal section sizes. LandscapeEditorObject's UI offers exactly
	 * these; a value outside the set produces a landscape whose component grid
	 * does not tile, and the failure surfaces much later as missing components.
	 */
	bool IsLegalQuadsPerSection(int32 InQuads)
	{
		return InQuads == 7 || InQuads == 15 || InQuads == 31
			|| InQuads == 63 || InQuads == 127 || InQuads == 255;
	}

#if WITH_EDITOR
	/**
	 * ONE DECLARATION of the Nanite build flags, read by both BuildLandscapeNanite
	 * and BuildLandscapeNaniteForProxies. Two call sites deriving their own flags
	 * is the shape non-negotiable 24 forbids: the batched build and the whole build
	 * would drift, and the difference would show up as a build that silently did
	 * not force, not as an error.
	 */
	UE::Landscape::EBuildFlags MakeNaniteBuildFlags(bool bForceRebuild)
	{
		UE::Landscape::EBuildFlags Flags = UE::Landscape::EBuildFlags::WriteFinalLog;
		if (bForceRebuild)
		{
			Flags |= UE::Landscape::EBuildFlags::ForceRebuild;
		}
		return Flags;
	}
#endif // WITH_EDITOR

	UWorld* GetEditorWorldChecked(FString& OutError)
	{
		if (GEditor == nullptr)
		{
			OutError = TEXT("GEditor is null. This is an editor-only operation.");
			return nullptr;
		}

		UWorld* World = GEditor->GetEditorWorldContext().World();
		if (World == nullptr)
		{
			OutError = TEXT("No editor world. Open a level first.");
			return nullptr;
		}

		if (World->GetCurrentLevel() == nullptr || !World->GetCurrentLevel()->bIsVisible)
		{
			OutError = TEXT("The current level is not visible; a landscape cannot be spawned into it.");
			return nullptr;
		}

		return World;
	}
}

ALandscape* ULandscapeLabTools::CreateLandscapeFromHeightmap(
	const FString& HeightmapPath,
	FVector Location,
	FRotator Rotation,
	FVector Scale,
	int32 SectionsPerComponent,
	int32 QuadsPerSection,
	int32 ComponentCountX,
	int32 ComponentCountY,
	UMaterialInterface* LandscapeMaterial,
	int32 WorldPartitionGridSize,
	const FString& ActorLabel,
	bool bFlipYAxis,
	bool bCenterOnLocation,
	FString& OutError)
{
	OutError.Empty();

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return nullptr;
#else

	// ---- Refuse before touching the world -------------------------------
	// Every check below runs before the actor is spawned, so a rejected call
	// leaves the level exactly as it was. This ordering is deliberate: this
	// project has already paid for a builder that validated after its
	// destructive step and died mid-rebuild on an input it could have refused.

	if (SectionsPerComponent != 1 && SectionsPerComponent != 2)
	{
		OutError = FString::Printf(
			TEXT("SectionsPerComponent must be 1 or 2, got %d. (The documented '1 or 4' is wrong.)"),
			SectionsPerComponent);
		return nullptr;
	}

	if (!IsLegalQuadsPerSection(QuadsPerSection))
	{
		OutError = FString::Printf(
			TEXT("QuadsPerSection must be one of 7/15/31/63/127/255, got %d."),
			QuadsPerSection);
		return nullptr;
	}

	if (ComponentCountX < 1 || ComponentCountY < 1)
	{
		OutError = FString::Printf(
			TEXT("ComponentCount must be >= 1 on both axes, got %d x %d."),
			ComponentCountX, ComponentCountY);
		return nullptr;
	}

	if (Scale.X == 0.0 || Scale.Y == 0.0 || Scale.Z == 0.0)
	{
		OutError = FString::Printf(TEXT("Scale has a zero component: %s."), *Scale.ToString());
		return nullptr;
	}

	if (!FPaths::FileExists(HeightmapPath))
	{
		OutError = FString::Printf(TEXT("Heightmap not found: %s"), *HeightmapPath);
		return nullptr;
	}

	UWorld* World = GetEditorWorldChecked(OutError);
	if (World == nullptr)
	{
		return nullptr;
	}

	const int32 QuadsPerComponent = SectionsPerComponent * QuadsPerSection;
	const int32 SizeX = ComponentCountX * QuadsPerComponent + 1;
	const int32 SizeY = ComponentCountY * QuadsPerComponent + 1;

	// ---- Read the heightmap, at exactly the resolution we asked for -----

	FLandscapeImportDescriptor ImportDescriptor;
	FText ImportMessage;

	const ELandscapeImportResult DescriptorResult =
		FLandscapeImportHelper::GetHeightmapImportDescriptor(
			HeightmapPath, /*bSingleFile=*/true, bFlipYAxis, ImportDescriptor, ImportMessage);

	if (DescriptorResult == ELandscapeImportResult::Error)
	{
		OutError = FString::Printf(TEXT("Could not read heightmap '%s': %s"),
			*HeightmapPath, *ImportMessage.ToString());
		return nullptr;
	}

	const int32 DescriptorIndex = ImportDescriptor.FindDescriptorIndex(SizeX, SizeY);
	if (DescriptorIndex == INDEX_NONE)
	{
		// Name both numbers AND what the file actually is. "resolution mismatch"
		// without the two figures sends the reader back to the file to find out
		// which way it is wrong.
		FString Offered;
		for (const FLandscapeImportResolution& Res : ImportDescriptor.ImportResolutions)
		{
			Offered += FString::Printf(TEXT(" %ux%u"), Res.Width, Res.Height);
		}
		if (Offered.IsEmpty())
		{
			Offered = TEXT(" (none)");
		}

		OutError = FString::Printf(
			TEXT("Heightmap '%s' does not match the requested layout. ")
			TEXT("Requested %d x %d (= %d components x %d sections x %d quads + 1). ")
			TEXT("File offers:%s. REFUSED rather than resampled."),
			*HeightmapPath, SizeX, SizeY,
			ComponentCountX, SectionsPerComponent, QuadsPerSection, *Offered);
		return nullptr;
	}

	TArray<uint16> HeightData;
	const ELandscapeImportResult DataResult =
		FLandscapeImportHelper::GetHeightmapImportData(
			ImportDescriptor, DescriptorIndex, HeightData, ImportMessage);

	if (DataResult == ELandscapeImportResult::Error)
	{
		OutError = FString::Printf(TEXT("Could not decode heightmap '%s': %s"),
			*HeightmapPath, *ImportMessage.ToString());
		return nullptr;
	}

	// A post-read assertion rather than trust: the descriptor said the file is
	// SizeX x SizeY, and this checks that the bytes agree with the descriptor.
	// Two representations of the same claim, and the cheap one is free.
	const int64 ExpectedSamples = static_cast<int64>(SizeX) * static_cast<int64>(SizeY);
	if (static_cast<int64>(HeightData.Num()) != ExpectedSamples)
	{
		OutError = FString::Printf(
			TEXT("Heightmap '%s' decoded to %d samples, expected %lld (%d x %d). REFUSED."),
			*HeightmapPath, HeightData.Num(), ExpectedSamples, SizeX, SizeY);
		return nullptr;
	}

	UE_LOG(LogLandscapeLab, Display,
		TEXT("CreateLandscapeFromHeightmap: %s -> %d x %d (%lld samples), %d x %d components, "
			 "%d sections x %d quads, scale %s"),
		*HeightmapPath, SizeX, SizeY, ExpectedSamples,
		ComponentCountX, ComponentCountY, SectionsPerComponent, QuadsPerSection, *Scale.ToString());

	// ---- Spawn and import ----------------------------------------------

	FVector SpawnLocation = Location;
	if (bCenterOnLocation)
	{
		const FVector Offset = FTransform(Rotation, FVector::ZeroVector, Scale).TransformVector(
			FVector(-ComponentCountX * QuadsPerComponent / 2.0,
					-ComponentCountY * QuadsPerComponent / 2.0,
					0.0));
		SpawnLocation = Location + Offset;
	}

	ALandscape* Landscape = World->SpawnActor<ALandscape>(SpawnLocation, Rotation);
	if (Landscape == nullptr)
	{
		OutError = TEXT("SpawnActor<ALandscape> returned null.");
		return nullptr;
	}

	Landscape->LandscapeMaterial = LandscapeMaterial;
	Landscape->SetActorRelativeScale3D(Scale);

	// Lighting LOD that will not crash Lightmass, taken verbatim from
	// LandscapeEditorDetailCustomization_NewLandscape.cpp:1226.
	Landscape->StaticLightingLOD = FMath::DivideAndRoundUp(
		FMath::CeilLogTwo((SizeX * SizeY) / (2048 * 2048) + 1), static_cast<uint32>(2));

	TMap<FGuid, TArray<uint16>> HeightDataPerLayers;
	HeightDataPerLayers.Add(FGuid(), MoveTemp(HeightData));

	TMap<FGuid, TArray<FLandscapeImportLayerInfo>> MaterialLayerDataPerLayers;
	MaterialLayerDataPerLayers.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());

	Landscape->Import(
		FGuid::NewGuid(),
		0, 0, SizeX - 1, SizeY - 1,
		SectionsPerComponent, QuadsPerSection,
		HeightDataPerLayers,
		*HeightmapPath,
		MaterialLayerDataPerLayers,
		ELandscapeImportAlphamapType::Additive,
		TArrayView<const FLandscapeLayer>());

	ULandscapeInfo* LandscapeInfo = Landscape->GetLandscapeInfo();
	if (LandscapeInfo == nullptr)
	{
		// The landscape exists but is not registered. Say so rather than
		// returning it as if the import had worked.
		OutError = TEXT("Import completed but GetLandscapeInfo() is null; the landscape is not registered.");
		return nullptr;
	}

	if (!ActorLabel.IsEmpty())
	{
		Landscape->SetActorLabel(ActorLabel);
	}

	LandscapeInfo->UpdateLayerInfoMap(Landscape);

	// ---- Split into World Partition proxies ------------------------------

	if (WorldPartitionGridSize > 0)
	{
		ULandscapeSubsystem* Subsystem = World->GetSubsystem<ULandscapeSubsystem>();
		if (Subsystem == nullptr)
		{
			OutError = TEXT("Landscape imported, but ULandscapeSubsystem is null so the grid size was NOT applied.");
			return Landscape;
		}

		if (!Subsystem->IsGridBased())
		{
			OutError = TEXT("Landscape imported, but this world is not grid based (no World Partition) "
							"so WorldPartitionGridSize was NOT applied.");
			return Landscape;
		}

		Subsystem->ChangeGridSize(LandscapeInfo, static_cast<uint32>(WorldPartitionGridSize));
	}

	return Landscape;
#endif // WITH_EDITOR
}

void ULandscapeLabTools::GetHeightmapResolution(
	const FString& HeightmapPath,
	int32& OutWidth,
	int32& OutHeight,
	bool& bOutSuccess,
	FString& OutError)
{
	OutError.Empty();
	OutWidth = 0;
	OutHeight = 0;
	bOutSuccess = false;

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return;
#else
	if (!FPaths::FileExists(HeightmapPath))
	{
		OutError = FString::Printf(TEXT("Heightmap not found: %s"), *HeightmapPath);
		return;
	}

	FLandscapeImportDescriptor ImportDescriptor;
	FText ImportMessage;

	const ELandscapeImportResult Result = FLandscapeImportHelper::GetHeightmapImportDescriptor(
		HeightmapPath, /*bSingleFile=*/true, /*bFlipYAxis=*/false, ImportDescriptor, ImportMessage);

	if (Result == ELandscapeImportResult::Error)
	{
		OutError = FString::Printf(TEXT("Could not read heightmap '%s': %s"),
			*HeightmapPath, *ImportMessage.ToString());
		return;
	}

	if (ImportDescriptor.FileResolutions.Num() == 0)
	{
		// Distinguish "I looked and it is absent" from "I could not look":
		// a readable file with no resolution is not a 0x0 heightmap.
		OutError = FString::Printf(
			TEXT("Heightmap '%s' was read but reports no resolution. Not returning 0 x 0 as a measurement."),
			*HeightmapPath);
		return;
	}

	OutWidth = static_cast<int32>(ImportDescriptor.FileResolutions[0].Width);
	OutHeight = static_cast<int32>(ImportDescriptor.FileResolutions[0].Height);
	bOutSuccess = true;
#endif
}

void ULandscapeLabTools::BuildLandscapeNanite(bool bForceRebuild, bool& bOutSuccess, FString& OutError)
{
	OutError.Empty();
	bOutSuccess = false;

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return;
#else
	UWorld* World = GetEditorWorldChecked(OutError);
	if (World == nullptr)
	{
		return;
	}

	ULandscapeSubsystem* Subsystem = World->GetSubsystem<ULandscapeSubsystem>();
	if (Subsystem == nullptr)
	{
		OutError = TEXT("ULandscapeSubsystem is null for the editor world.");
		return;
	}

	// An empty view means "every registered proxy" (LandscapeSubsystem.cpp:1124-1133).
	// That is deliberate here and is what this function is for; the batched form
	// refuses the same value.
	Subsystem->BuildNanite(MakeNaniteBuildFlags(bForceRebuild), TArrayView<ALandscapeProxy*>());
	bOutSuccess = true;
#endif
}

void ULandscapeLabTools::BuildLandscapeNaniteForProxies(
	const TArray<ALandscapeProxy*>& ProxiesToBuild,
	bool bForceRebuild,
	int32& OutProxiesSubmitted,
	int32& OutProxiesAlreadyUpToDate,
	bool& bOutSuccess,
	FString& OutError)
{
	OutError.Empty();
	bOutSuccess = false;
	OutProxiesSubmitted = 0;
	OutProxiesAlreadyUpToDate = 0;

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return;
#else
	// REFUSE FIRST, TOUCH NOTHING. Every check below runs before the subsystem is
	// contacted, so a bad batch cannot half-run.
	if (ProxiesToBuild.IsEmpty())
	{
		OutError = TEXT("Refused: the proxy list is empty. An empty list means BUILD EVERY "
						"PROXY to ULandscapeSubsystem::BuildNanite (LandscapeSubsystem.cpp:1124-1133), "
						"which is the unbounded build this function exists to avoid. Pass the "
						"batch explicitly, or call BuildLandscapeNanite if you really want all of them.");
		return;
	}

	UWorld* World = GetEditorWorldChecked(OutError);
	if (World == nullptr)
	{
		return;
	}

	ULandscapeSubsystem* Subsystem = World->GetSubsystem<ULandscapeSubsystem>();
	if (Subsystem == nullptr)
	{
		OutError = TEXT("ULandscapeSubsystem is null for the editor world.");
		return;
	}

	for (int32 Index = 0; Index < ProxiesToBuild.Num(); ++Index)
	{
		ALandscapeProxy* Proxy = ProxiesToBuild[Index];

		if (Proxy == nullptr)
		{
			// The subsystem drops nulls silently at :1156. A batch of 8 that was
			// really a batch of 7 would look like a completed batch.
			OutError = FString::Printf(
				TEXT("Refused: entry %d is null. The subsystem drops nulls silently "
					 "(LandscapeSubsystem.cpp:1156), so a batch short of what was asked for "
					 "would report as complete."), Index);
			return;
		}

		if (Proxy->GetWorld() != World)
		{
			OutError = FString::Printf(
				TEXT("Refused: entry %d ('%s') does not belong to the editor world."),
				Index, *Proxy->GetActorNameOrLabel());
			return;
		}

		// The parent trap. BuildNanite expands an ALandscape to every streaming
		// proxy it owns (LandscapeSubsystem.cpp:1140-1147), so one parent actor in
		// a batch of eight is silently a batch of 256 and the memory bound is gone.
		if (ALandscape* Landscape = Cast<ALandscape>(Proxy))
		{
			int32 StreamingProxyCount = 0;
			if (ULandscapeInfo* LandscapeInfo = Landscape->GetLandscapeInfo())
			{
				StreamingProxyCount = LandscapeInfo->GetSortedStreamingProxies().Num();
			}

			if (StreamingProxyCount > 0)
			{
				OutError = FString::Printf(
					TEXT("Refused: entry %d ('%s') is the parent ALandscape, which the subsystem "
						 "expands to all %d of its streaming proxies (LandscapeSubsystem.cpp:1140-1147). "
						 "This batch of %d would have become %d. Pass the streaming proxies themselves."),
					Index, *Landscape->GetActorNameOrLabel(), StreamingProxyCount,
					ProxiesToBuild.Num(), StreamingProxyCount);
				return;
			}
			// An ALandscape with no streaming proxies owns its own components and is
			// a legitimate single-actor batch on a non-partitioned world.
		}

		// A Nanite-disabled proxy is not an error the engine reports -- it is an
		// error the engine IGNORES. UpdateNaniteRepresentationAsync's whole body is
		// behind IsNaniteEnabled() (Landscape.cpp:465), so submitting one returns
		// success and builds nothing, and IsNaniteMeshUpToDate() calls it up to
		// date into the bargain (Landscape.cpp:445). Refuse instead.
		if (!Proxy->IsNaniteEnabled())
		{
			OutError = FString::Printf(
				TEXT("Refused: entry %d ('%s') has Nanite disabled. "
					 "UpdateNaniteRepresentationAsync does nothing without it "
					 "(Landscape.cpp:465) and would report success. Set enable_nanite first."),
				Index, *Proxy->GetActorNameOrLabel());
			return;
		}

		// Measured here, before the call, because the subsystem removes up-to-date
		// proxies from its own list (:1156) and then reports the REMAINING count.
		// Without this the caller cannot tell an already-built batch from a no-op.
		if (Proxy->IsNaniteMeshUpToDate())
		{
			++OutProxiesAlreadyUpToDate;
		}
	}

	// The array is validated; copy it because TArrayView<ALandscapeProxy*> is a view
	// of NON-const elements and the parameter is a const reference.
	TArray<ALandscapeProxy*> Batch(ProxiesToBuild);
	OutProxiesSubmitted = Batch.Num();

	UE_LOG(LogLandscapeLab, Display,
		TEXT("BuildLandscapeNaniteForProxies: submitting %d proxies (%d already up to date), bForceRebuild=%d"),
		OutProxiesSubmitted, OutProxiesAlreadyUpToDate, bForceRebuild ? 1 : 0);

	Subsystem->BuildNanite(MakeNaniteBuildFlags(bForceRebuild), TArrayView<ALandscapeProxy*>(Batch));
	bOutSuccess = true;
#endif
}

void ULandscapeLabTools::LoadAllWorldPartitionRegions(
	bool& bOutSuccess,
	FVector& OutBoundsMin,
	FVector& OutBoundsMax,
	FString& OutError)
{
	OutError.Empty();
	bOutSuccess = false;
	OutBoundsMin = FVector::ZeroVector;
	OutBoundsMax = FVector::ZeroVector;

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return;
#else
	UWorld* World = GetEditorWorldChecked(OutError);
	if (World == nullptr)
	{
		return;
	}

	UWorldPartition* WorldPartition = World->GetWorldPartition();
	if (WorldPartition == nullptr)
	{
		// Say which of the two it is. "Could not load regions" on a
		// non-partitioned world reads as a failure when it is a category error.
		OutError = TEXT("This world is not World Partition; there are no regions to load. "
						"Everything in it is already resident.");
		return;
	}

	const FBox WorldBounds = WorldPartition->GetEditorWorldBounds();
	if (!WorldBounds.IsValid)
	{
		OutError = TEXT("GetEditorWorldBounds() returned an invalid box. This is "
						"'could not determine what to load', not 'there is nothing to load'.");
		return;
	}

	// XY from the world bounds, Z forced wide -- same shape the region tool
	// uses (SWorldPartitionEditorGrid2D.cpp:703). A Z range derived from
	// current contents would silently exclude anything outside it.
	const FBox LoadBox(
		FVector(WorldBounds.Min.X, WorldBounds.Min.Y, -HALF_WORLD_MAX),
		FVector(WorldBounds.Max.X, WorldBounds.Max.Y, HALF_WORLD_MAX));

	UWorldPartitionEditorLoaderAdapter* EditorLoaderAdapter =
		WorldPartition->CreateEditorLoaderAdapter<FLoaderAdapterShape>(
			World, LoadBox, TEXT("LandscapeLab LoadAllRegions"));

	if (EditorLoaderAdapter == nullptr || EditorLoaderAdapter->GetLoaderAdapter() == nullptr)
	{
		OutError = TEXT("CreateEditorLoaderAdapter returned no usable adapter.");
		return;
	}

	EditorLoaderAdapter->GetLoaderAdapter()->SetUserCreated(true);
	EditorLoaderAdapter->GetLoaderAdapter()->Load();

	// Assert the adapter believes it loaded, rather than assuming Load()
	// succeeded because it returned. This is a check on the operation, not on
	// the scene -- the caller still has to census what arrived.
	if (!EditorLoaderAdapter->GetLoaderAdapter()->IsLoaded())
	{
		OutError = TEXT("Load() completed but the adapter does not report IsLoaded(). "
						"Treat the world as PARTIALLY loaded, not as loaded.");
		OutBoundsMin = LoadBox.Min;
		OutBoundsMax = LoadBox.Max;
		return;
	}

	OutBoundsMin = LoadBox.Min;
	OutBoundsMax = LoadBox.Max;
	bOutSuccess = true;

	UE_LOG(LogLandscapeLab, Display,
		TEXT("LoadAllWorldPartitionRegions: loaded XY [%f..%f, %f..%f]"),
		WorldBounds.Min.X, WorldBounds.Max.X, WorldBounds.Min.Y, WorldBounds.Max.Y);
#endif
}

void ULandscapeLabTools::ChangeLandscapeGridSize(
	ALandscape* Landscape,
	int32 NewGridSizeInComponents,
	bool& bOutSuccess,
	FString& OutError)
{
	OutError.Empty();
	bOutSuccess = false;

#if !WITH_EDITOR
	OutError = TEXT("Built without WITH_EDITOR.");
	return;
#else
	if (Landscape == nullptr)
	{
		OutError = TEXT("Landscape is null.");
		return;
	}

	if (NewGridSizeInComponents < 1)
	{
		OutError = FString::Printf(TEXT("NewGridSizeInComponents must be >= 1, got %d."),
			NewGridSizeInComponents);
		return;
	}

	UWorld* World = Landscape->GetWorld();
	if (World == nullptr)
	{
		OutError = TEXT("Landscape has no world.");
		return;
	}

	ULandscapeInfo* LandscapeInfo = Landscape->GetLandscapeInfo();
	if (LandscapeInfo == nullptr)
	{
		OutError = TEXT("Landscape has no ULandscapeInfo; it is not registered.");
		return;
	}

	ULandscapeSubsystem* Subsystem = World->GetSubsystem<ULandscapeSubsystem>();
	if (Subsystem == nullptr)
	{
		OutError = TEXT("ULandscapeSubsystem is null for this landscape's world.");
		return;
	}

	if (!Subsystem->IsGridBased())
	{
		OutError = TEXT("This world is not grid based (no World Partition); grid size does not apply.");
		return;
	}

	Subsystem->ChangeGridSize(LandscapeInfo, static_cast<uint32>(NewGridSizeInComponents));
	bOutSuccess = true;
#endif
}

// =========================================================================
// MetaHuman DNA — neutral joint translations
// =========================================================================

void ULandscapeLabTools::ReadDNAJoints(
	const FString& DNAPath,
	TArray<FString>& OutJointNames,
	TArray<FVector>& OutTranslations,
	int32& OutJointCount,
	FString& OutFormat,
	bool& bOutSuccess,
	FString& OutError)
{
	OutJointNames.Reset();
	OutTranslations.Reset();
	OutJointCount = 0;
	OutFormat.Reset();
	bOutSuccess = false;
	OutError.Reset();

	if (!FPaths::FileExists(DNAPath))
	{
		OutError = FString::Printf(TEXT("No such DNA file: %s"), *DNAPath);
		return;
	}

	TSharedPtr<IDNAReader> Reader = LoadDNAFromFile(DNAPath);
	if (!Reader.IsValid())
	{
		// A null reader and an empty DNA are different things, and only one
		// of them is a file we can work with. Say which happened.
		OutError = FString::Printf(
			TEXT("LoadDNAFromFile returned no reader for %s. The file exists ")
			TEXT("but did not parse as DNA."), *DNAPath);
		return;
	}

	OutFormat = FString::Printf(TEXT("%d.%d (gen %d, ver %d)"),
		Reader->GetFileFormatGeneration(), Reader->GetFileFormatVersion(),
		Reader->GetFileFormatGeneration(), Reader->GetFileFormatVersion());

	const uint16 JointCount = Reader->GetJointCount();
	OutJointCount = static_cast<int32>(JointCount);
	OutJointNames.Reserve(JointCount);
	OutTranslations.Reserve(JointCount);
	for (uint16 i = 0; i < JointCount; ++i)
	{
		OutJointNames.Add(Reader->GetJointName(i));
		OutTranslations.Add(Reader->GetNeutralJointTranslation(i));
	}

	bOutSuccess = true;
}

void ULandscapeLabTools::WriteDNAJointTranslations(
	const FString& InDNAPath,
	const FString& OutDNAPath,
	const TArray<int32>& JointIndices,
	const TArray<FVector>& NewTranslations,
	int32& OutJointCount,
	FString& OutLayerNote,
	bool& bOutSuccess,
	FString& OutError)
{
	OutJointCount = 0;
	OutLayerNote.Reset();
	bOutSuccess = false;
	OutError.Reset();

	// ---- refusals, all of them BEFORE anything is read or written ------
	if (!FPaths::FileExists(InDNAPath))
	{
		OutError = FString::Printf(TEXT("No such DNA file: %s"), *InDNAPath);
		return;
	}
	if (JointIndices.Num() != NewTranslations.Num())
	{
		OutError = FString::Printf(
			TEXT("JointIndices has %d entries and NewTranslations has %d. ")
			TEXT("They are parallel arrays; a mismatch would silently pair ")
			TEXT("the wrong translation with the wrong joint."),
			JointIndices.Num(), NewTranslations.Num());
		return;
	}
	if (JointIndices.Num() == 0)
	{
		OutError = TEXT("No joints given. Refusing to write a file identical ")
			TEXT("to its input, which would read as a successful edit.");
		return;
	}

	// IN-PLACE IS REFUSED. The canonical DNA is the only thing that puts the
	// head back after an import_whole_rig replaces the rig.
	const FString InFull = FPaths::ConvertRelativePathToFull(InDNAPath);
	const FString OutFull = FPaths::ConvertRelativePathToFull(OutDNAPath);
	if (InFull.Equals(OutFull, ESearchCase::IgnoreCase))
	{
		OutError = FString::Printf(
			TEXT("OutDNAPath is the same file as InDNAPath (%s). In-place ")
			TEXT("editing of a DNA is refused: it is the only restore point ")
			TEXT("for the head."), *InFull);
		return;
	}

	TSharedPtr<IDNAReader> Reader = LoadDNAFromFile(InDNAPath);
	if (!Reader.IsValid())
	{
		OutError = FString::Printf(
			TEXT("LoadDNAFromFile returned no reader for %s."), *InDNAPath);
		return;
	}

	const uint16 JointCount = Reader->GetJointCount();
	OutJointCount = static_cast<int32>(JointCount);

	TSet<int32> Seen;
	for (int32 k = 0; k < JointIndices.Num(); ++k)
	{
		const int32 Idx = JointIndices[k];
		if (Idx < 0 || Idx >= static_cast<int32>(JointCount))
		{
			OutError = FString::Printf(
				TEXT("JointIndices[%d] = %d is outside [0, %d)."),
				k, Idx, static_cast<int32>(JointCount));
			return;
		}
		bool bAlready = false;
		Seen.Add(Idx, &bAlready);
		if (bAlready)
		{
			OutError = FString::Printf(
				TEXT("Joint index %d appears more than once. The last would ")
				TEXT("silently win, so this is refused rather than resolved."),
				Idx);
			return;
		}
	}

	// ---- build the FULL translation array ------------------------------
	// The command sets EVERY joint at once, so untouched joints are carried
	// through from the source. Defaulting them would zero 800+ joints and
	// collapse the face.
	TArray<FVector> All;
	All.Reserve(JointCount);
	for (uint16 i = 0; i < JointCount; ++i)
	{
		All.Add(Reader->GetNeutralJointTranslation(i));
	}
	for (int32 k = 0; k < JointIndices.Num(); ++k)
	{
		All[JointIndices[k]] = NewTranslations[k];
	}

	// ---- run the command -----------------------------------------------
	// FDNACalibDNAReader does NOT take ownership of Reader: it calls
	// Unwrap() and creates its own dnac copy (DNACalibDNAReader.cpp:10-12).
	FDNACalibDNAReader Calib(Reader.Get());
	// The view is NAMED deliberately. Written inline as
	//   Command(TArrayView<const FVector>(All))
	// this is the most vexing parse: C++ reads it as a FUNCTION declaration
	// taking a TArrayView named All, and the next line fails with
	// "left of '.Run' must have class/struct/union" rather than anything
	// that mentions the real problem.
	const TArrayView<const FVector> TranslationView(All);
	FDNACalibSetNeutralJointTranslationsCommand Command(TranslationView);
	Command.Run(&Calib);

	SaveDNAToFile(&Calib, EDNADataLayer::All, OutDNAPath);

	OutLayerNote = FString::Printf(
		TEXT("EDIT touched DEFINITION (neutral joint translations, %d of %d ")
		TEXT("joints changed); WROTE EDNADataLayer::All to %s"),
		JointIndices.Num(), static_cast<int32>(JointCount), *OutDNAPath);

	// ---- SELF-VERIFY FROM THE ARTEFACT ---------------------------------
	// Re-load the file that was just written and compare. "The call
	// returned" is not evidence about the bytes on disk -- this project has
	// a save that reported success while writing nothing, and one that
	// reported failure over a success.
	if (!FPaths::FileExists(OutDNAPath))
	{
		OutError = FString::Printf(
			TEXT("SaveDNAToFile returned but %s does not exist."), *OutDNAPath);
		return;
	}
	TSharedPtr<IDNAReader> Back = LoadDNAFromFile(OutDNAPath);
	if (!Back.IsValid())
	{
		OutError = FString::Printf(
			TEXT("Wrote %s but it did not load back as DNA."), *OutDNAPath);
		return;
	}
	if (Back->GetJointCount() != JointCount)
	{
		OutError = FString::Printf(
			TEXT("Joint count changed across the write: %d in, %d out."),
			static_cast<int32>(JointCount),
			static_cast<int32>(Back->GetJointCount()));
		return;
	}
	const double Tol = 1e-4;
	for (int32 k = 0; k < JointIndices.Num(); ++k)
	{
		const int32 Idx = JointIndices[k];
		const FVector Got = Back->GetNeutralJointTranslation(
			static_cast<uint16>(Idx));
		const FVector Want = NewTranslations[k];
		if (FMath::Abs(Got.X - Want.X) > Tol ||
			FMath::Abs(Got.Y - Want.Y) > Tol ||
			FMath::Abs(Got.Z - Want.Z) > Tol)
		{
			OutError = FString::Printf(
				TEXT("Read-back disagrees at joint %d (%s): wrote ")
				TEXT("(%.6f, %.6f, %.6f), file says (%.6f, %.6f, %.6f)."),
				Idx, *Back->GetJointName(static_cast<uint16>(Idx)),
				Want.X, Want.Y, Want.Z, Got.X, Got.Y, Got.Z);
			return;
		}
	}

	bOutSuccess = true;
}

// -------------------------------------------------------------------------
// Applying a DNA to a SkeletalMesh, one stage at a time
// -------------------------------------------------------------------------

namespace
{
	/**
	 * Component-space translation of named bones, read out of a mesh's OWN
	 * reference skeleton. Composed by walking parents rather than by calling
	 * the animation runtime, so it depends on nothing but the ref skeleton
	 * itself -- the representation we want to compare against the DNA file.
	 *
	 * Returns false and names the offender if a bone is not present. A probe
	 * that silently skips a missing bone reports "nothing moved" for a bone
	 * nobody looked at.
	 */
	bool ProbeRefSkeletonComponentSpace(
		const USkeletalMesh* Mesh,
		const TArray<FString>& BoneNames,
		TArray<FVector>& OutTranslations,
		FString& OutError)
	{
		OutTranslations.Reset();
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		const TArray<FTransform>& Pose = Ref.GetRefBonePose();
		for (const FString& Name : BoneNames)
		{
			const int32 Index = Ref.FindBoneIndex(FName(*Name));
			if (Index == INDEX_NONE)
			{
				OutError = FString::Printf(
					TEXT("Probe bone '%s' is not in the reference skeleton ")
					TEXT("(%d bones). Refusing rather than reporting it as ")
					TEXT("unmoved."), *Name, Ref.GetNum());
				return false;
			}
			FTransform Accum = FTransform::Identity;
			int32 Walk = Index;
			int32 Guard = 0;
			while (Walk != INDEX_NONE && Guard++ <= Ref.GetNum())
			{
				Accum = Accum * Pose[Walk];
				Walk = Ref.GetParentIndex(Walk);
			}
			if (Guard > Ref.GetNum())
			{
				OutError = FString::Printf(
					TEXT("Parent walk for '%s' did not terminate; the ")
					TEXT("reference skeleton has a cycle."), *Name);
				return false;
			}
			OutTranslations.Add(Accum.GetTranslation());
		}
		return true;
	}
}

namespace
{
	const TCHAR* DirectionText(EDirection D)
	{
		switch (D)
		{
		case EDirection::Left:  return TEXT("Left");
		case EDirection::Right: return TEXT("Right");
		case EDirection::Up:    return TEXT("Up");
		case EDirection::Down:  return TEXT("Down");
		case EDirection::Front: return TEXT("Front");
		case EDirection::Back:  return TEXT("Back");
		}
		return TEXT("?");
	}

	/** What the reader DECLARES about itself. A DNA states its own axes and
	 *  units, so none of this has to be inferred from a magnitude. */
	FString DescribeReader(const IDNAReader* R)
	{
		// Every %s argument is bound to a named const TCHAR* first. A ternary
		// between two string LITERALS yields arrays of different lengths and
		// the format-string sanitizer rejects it.
		const FCoordinateSystem CS = R->GetCoordinateSystem();
		const TCHAR* const AxisX = DirectionText(CS.XAxis);
		const TCHAR* const AxisY = DirectionText(CS.YAxis);
		const TCHAR* const AxisZ = DirectionText(CS.ZAxis);
		const TCHAR* TransUnit = TEXT("m");
		if (R->GetTranslationUnit() == ETranslationUnit::CM)  // DNACommon.h:35
		{
			TransUnit = TEXT("cm");
		}
		const TCHAR* RotUnit = TEXT("radians");
		if (R->GetRotationUnit() == ERotationUnit::Degrees)
		{
			RotUnit = TEXT("degrees");
		}
		const TCHAR* Legacy = TEXT("no");
		if (R->IsLegacyWrapped())
		{
			Legacy = TEXT("YES");
		}
		return FString::Printf(
			TEXT("format %d.%d; axes X=%s Y=%s Z=%s; translation unit %s; ")
			TEXT("rotation unit %s; joints %d; legacy-wrapped %s"),
			static_cast<int32>(R->GetFileFormatGeneration()),
			static_cast<int32>(R->GetFileFormatVersion()),
			AxisX, AxisY, AxisZ, TransUnit, RotUnit,
			static_cast<int32>(R->GetJointCount()), Legacy);
	}
}

void ULandscapeLabTools::ApplyDNAToSkeletalMesh(
	const FString& DNAPath,
	const FString& ReaderSource,
	USkeletalMesh* Mesh,
	bool bUpdateJoints,
	bool bUpdateBaseMesh,
	bool bRebuildRenderData,
	bool bAttachDNA,
	const TArray<FString>& ProbeBoneNames,
	TArray<FVector>& OutProbeBefore,
	TArray<FVector>& OutProbeAfter,
	int32& OutBoneCount,
	FString& OutStagesRun,
	FString& OutReaderInfo,
	bool& bOutSuccess,
	FString& OutError)
{
	OutProbeBefore.Reset();
	OutProbeAfter.Reset();
	OutBoneCount = 0;
	OutStagesRun.Reset();
	OutReaderInfo.Reset();
	bOutSuccess = false;
	OutError.Reset();

#if !WITH_EDITORONLY_DATA
	OutError = TEXT("UpdateJoints/UpdateBaseMesh are WITH_EDITORONLY_DATA.");
	return;
#else
	if (Mesh == nullptr)
	{
		OutError = TEXT("Mesh is null.");
		return;
	}
	const FString Source = ReaderSource.IsEmpty()
		? FString(TEXT("file")) : ReaderSource.ToLower();
	if (Source != TEXT("file") && Source != TEXT("legacy")
		&& Source != TEXT("mesh"))
	{
		OutError = FString::Printf(
			TEXT("ReaderSource '%s' is not one of file / legacy / mesh."),
			*ReaderSource);
		return;
	}
	if (Source != TEXT("mesh") && !FPaths::FileExists(DNAPath))
	{
		OutError = FString::Printf(TEXT("No such DNA file: %s"), *DNAPath);
		return;
	}

	TSharedPtr<IDNAReader> Reader;
	if (Source == TEXT("file"))
	{
		Reader = LoadDNAFromFile(DNAPath);
	}
	else if (Source == TEXT("legacy"))
	{
		Reader = ReadDNAFromFile(DNAPath);
	}
	else
	{
		Reader = USkelMeshDNAUtils::GetDNAReader(Mesh);
	}
	if (!Reader.IsValid())
	{
		OutError = FString::Printf(
			TEXT("Reader source '%s' produced no reader (%s). A missing ")
			TEXT("reader and an empty DNA are different things."),
			*Source,
			Source == TEXT("mesh")
				? TEXT("the mesh carries no DNA") : *DNAPath);
		return;
	}
	OutReaderInfo = FString::Printf(TEXT("source=%s; %s"),
		*Source, *DescribeReader(Reader.Get()));

	OutBoneCount = Mesh->GetRefSkeleton().GetNum();
	if (!ProbeRefSkeletonComponentSpace(
			Mesh, ProbeBoneNames, OutProbeBefore, OutError))
	{
		return;
	}

	// A PROBE MUST NOT DIRTY THE PACKAGE. With every stage off this call is a
	// read, and marking it dirty would leave a Save Content modal waiting at
	// the next editor close -- a modal that blocks the game thread, which is
	// the only channel that could report it.
	const bool bWillMutate =
		bUpdateJoints || bUpdateBaseMesh || bRebuildRenderData || bAttachDNA;
	if (bWillMutate)
	{
		Mesh->Modify();
	}

	// The mapping must be built and its joint/morph tables populated before
	// any update stage reads it -- this is the engine's own order in
	// MetaHumanIdentityParts.cpp:1474-1482.
	TUniquePtr<FDNAToSkelMeshMap> Map(
		USkelMeshDNAUtils::CreateMapForUpdatingNeutralMesh(
			Reader.Get(), Mesh));
	if (!Map.IsValid())
	{
		OutError = TEXT(
			"CreateMapForUpdatingNeutralMesh returned null: this DNA and this "
			"mesh could not be mapped to each other.");
		return;
	}
	Map->MapJoints(Reader.Get());
	Map->MapMorphTargets(Reader.Get());
	OutStagesRun = TEXT("map");

	if (bAttachDNA)
	{
		USkelMeshDNAUtils::SetDNAReader(Mesh, Reader);
		OutStagesRun += TEXT(", attach");
	}
	if (bUpdateJoints)
	{
		USkelMeshDNAUtils::UpdateJoints(Mesh, Reader.Get(), Map.Get());
		OutStagesRun += TEXT(", joints(BIND POSE)");
	}
	if (bUpdateBaseMesh)
	{
		USkelMeshDNAUtils::UpdateBaseMesh(
			Mesh, Reader.Get(), Map.Get(), ELodUpdateOption::All);
		OutStagesRun += TEXT(", basemesh(VERTICES, all LODs)");
	}

	if (bRebuildRenderData)
	{
		USkelMeshDNAUtils::RebuildRenderData(Mesh);
		OutStagesRun += TEXT(", rebuild(full)");
	}
	else if (bUpdateJoints || bUpdateBaseMesh)
	{
		USkelMeshDNAUtils::RebuildRenderData_VertexPosition(Mesh);
		OutStagesRun += TEXT(", rebuild(vertex position)");
	}

	if (bWillMutate)
	{
		Mesh->MarkPackageDirty();
	}

	if (!ProbeRefSkeletonComponentSpace(
			Mesh, ProbeBoneNames, OutProbeAfter, OutError))
	{
		return;
	}

	bOutSuccess = true;
#endif
}

// -------------------------------------------------------------------------
// MetaHuman DNA — GEOMETRY
//
// Joints are not the lever. Measured 2026-08-17: a neutral-joint-translation
// edit is invisible through import_from_face_dna, because FitToFaceDna fits
// the parametric state to the DNA's GEOMETRY and never reads the neutral
// joints. Writing joints is dead weight and a false audit trail. These two
// functions are the geometry-first replacement.
// -------------------------------------------------------------------------

void ULandscapeLabTools::ReadDNAMeshes(
	const FString& DNAPath,
	TArray<FString>& OutMeshNames,
	TArray<int32>& OutVertexCounts,
	TArray<FVector>& OutBoundsMin,
	TArray<FVector>& OutBoundsMax,
	int32& OutMeshCount,
	FString& OutReaderInfo,
	bool& bOutSuccess,
	FString& OutError)
{
	OutMeshNames.Reset();
	OutVertexCounts.Reset();
	OutBoundsMin.Reset();
	OutBoundsMax.Reset();
	OutMeshCount = 0;
	OutReaderInfo.Reset();
	bOutSuccess = false;
	OutError.Reset();

	if (!FPaths::FileExists(DNAPath))
	{
		OutError = FString::Printf(TEXT("No such DNA file: %s"), *DNAPath);
		return;
	}
	TSharedPtr<IDNAReader> Reader = LoadDNAFromFile(DNAPath);
	if (!Reader.IsValid())
	{
		OutError = FString::Printf(
			TEXT("LoadDNAFromFile returned no reader for %s."), *DNAPath);
		return;
	}
	OutReaderInfo = DescribeReader(Reader.Get());

	const uint16 MeshCount = Reader->GetMeshCount();
	OutMeshCount = static_cast<int32>(MeshCount);
	for (uint16 i = 0; i < MeshCount; ++i)
	{
		OutMeshNames.Add(Reader->GetMeshName(i));
		const uint32 Count = Reader->GetVertexPositionCount(i);
		OutVertexCounts.Add(static_cast<int32>(Count));

		// A mesh with no vertices gets a ZERO box, and the count beside it
		// says which it is. An empty box that looked like a real one at the
		// origin would send a region edit somewhere arbitrary.
		FVector Min(0.0), Max(0.0);
		if (Count > 0)
		{
			Min = FVector(TNumericLimits<double>::Max());
			Max = FVector(TNumericLimits<double>::Lowest());
			for (uint32 v = 0; v < Count; ++v)
			{
				const FVector P = Reader->GetVertexPosition(i, v);
				Min.X = FMath::Min(Min.X, P.X);
				Min.Y = FMath::Min(Min.Y, P.Y);
				Min.Z = FMath::Min(Min.Z, P.Z);
				Max.X = FMath::Max(Max.X, P.X);
				Max.Y = FMath::Max(Max.Y, P.Y);
				Max.Z = FMath::Max(Max.Z, P.Z);
			}
		}
		OutBoundsMin.Add(Min);
		OutBoundsMax.Add(Max);
	}
	bOutSuccess = true;
}

void ULandscapeLabTools::WriteDNAVertexDeltaInBox(
	const FString& InDNAPath,
	const FString& OutDNAPath,
	int32 MeshIndex,
	FVector BoxMin,
	FVector BoxMax,
	FVector Delta,
	float FeatherBandCm,
	int32& OutCoreCount,
	int32& OutSelectedCount,
	int32& OutVertexCount,
	FString& OutLayerNote,
	bool& bOutSuccess,
	FString& OutError)
{
	OutCoreCount = 0;
	OutSelectedCount = 0;
	OutVertexCount = 0;
	OutLayerNote.Reset();
	bOutSuccess = false;
	OutError.Reset();

	if (!FPaths::FileExists(InDNAPath))
	{
		OutError = FString::Printf(TEXT("No such DNA file: %s"), *InDNAPath);
		return;
	}
	// Never edit the canonical DNA in place. It is the only thing that puts
	// the head back, and this project has already lost a hero to content it
	// could not restore.
	const FString InFull = FPaths::ConvertRelativePathToFull(InDNAPath);
	const FString OutFull = FPaths::ConvertRelativePathToFull(OutDNAPath);
	if (InFull.Equals(OutFull, ESearchCase::IgnoreCase))
	{
		OutError = TEXT("Refusing to write the DNA over its own input.");
		return;
	}
	if (BoxMin.X >= BoxMax.X || BoxMin.Y >= BoxMax.Y || BoxMin.Z >= BoxMax.Z)
	{
		OutError = FString::Printf(
			TEXT("Degenerate box: min (%.4f, %.4f, %.4f) is not strictly ")
			TEXT("below max (%.4f, %.4f, %.4f) on every axis."),
			BoxMin.X, BoxMin.Y, BoxMin.Z, BoxMax.X, BoxMax.Y, BoxMax.Z);
		return;
	}

	TSharedPtr<IDNAReader> Reader = LoadDNAFromFile(InDNAPath);
	if (!Reader.IsValid())
	{
		OutError = FString::Printf(
			TEXT("LoadDNAFromFile returned no reader for %s."), *InDNAPath);
		return;
	}

	const int32 MeshCount = static_cast<int32>(Reader->GetMeshCount());
	if (MeshIndex < 0 || MeshIndex >= MeshCount)
	{
		OutError = FString::Printf(
			TEXT("MeshIndex %d is outside [0, %d)."), MeshIndex, MeshCount);
		return;
	}
	const uint16 Mesh = static_cast<uint16>(MeshIndex);
	const uint32 VertexCount = Reader->GetVertexPositionCount(Mesh);
	OutVertexCount = static_cast<int32>(VertexCount);
	if (VertexCount == 0)
	{
		OutError = FString::Printf(
			TEXT("Mesh %d (%s) has no vertices."),
			MeshIndex, *Reader->GetMeshName(Mesh));
		return;
	}

	if (FeatherBandCm < 0.0f)
	{
		OutError = FString::Printf(
			TEXT("FeatherBandCm is %.4f; a negative band has no meaning."),
			FeatherBandCm);
		return;
	}

	// READ ALL, MODIFY SOME, WRITE ALL. DNACalib replaces every position of
	// the mesh at once, so the untouched vertices have to be carried through
	// from the source rather than defaulted.
	//
	// THE BOX IS THE CORE AND THE BAND IS THE BRUSH. Weight is 1.0 inside the
	// box and falls smoothstep to 0.0 at BoxMin/Max expanded by the band,
	// measured by distance from the box. A hard edge would change the
	// attenuation being measured, so the shape of this falloff is part of
	// the measurement and is reported with it.
	const double Band = static_cast<double>(FeatherBandCm);
	TArray<FVector> Original;
	TArray<FVector> Positions;
	TArray<float> Masks;
	Original.Reserve(VertexCount);
	Positions.Reserve(VertexCount);
	Masks.Reserve(VertexCount);
	TArray<int32> Selected;
	int32 CoreCount = 0;
	for (uint32 i = 0; i < VertexCount; ++i)
	{
		const FVector P = Reader->GetVertexPosition(Mesh, i);
		Original.Add(P);

		// Distance from the core box: zero inside, else the Euclidean
		// distance to its surface.
		const double dx = FMath::Max3(BoxMin.X - P.X, 0.0, P.X - BoxMax.X);
		const double dy = FMath::Max3(BoxMin.Y - P.Y, 0.0, P.Y - BoxMax.Y);
		const double dz = FMath::Max3(BoxMin.Z - P.Z, 0.0, P.Z - BoxMax.Z);
		const double Dist = FMath::Sqrt(dx * dx + dy * dy + dz * dz);

		double W = 0.0;
		if (Dist <= 0.0)
		{
			W = 1.0;
			++CoreCount;
		}
		else if (Band > 0.0 && Dist < Band)
		{
			const double t = Dist / Band;
			// smoothstep, inverted so W is 1 at the core and 0 at the edge
			W = 1.0 - (t * t * (3.0 - 2.0 * t));
		}

		Masks.Add(static_cast<float>(W));
		// Every vertex is offered original + Delta; the MASK decides how
		// much of it lands.
		Positions.Add(P + Delta);
		if (W > 0.0)
		{
			Selected.Add(static_cast<int32>(i));
		}
	}
	OutCoreCount = CoreCount;
	OutSelectedCount = Selected.Num();
	if (Selected.Num() == 0)
	{
		// An edit that reports success while moving nothing is the false
		// audit trail this whole geometry route exists to replace.
		OutError = FString::Printf(
			TEXT("No vertex of mesh %d (%s) falls inside the box; refusing ")
			TEXT("to write a DNA identical to its input. The box is in the ")
			TEXT("DNA's OWN space -- this file declares: %s"),
			MeshIndex, *Reader->GetMeshName(Mesh),
			*DescribeReader(Reader.Get()));
		return;
	}
	FDNACalibDNAReader Calib(Reader.Get());
	const TArrayView<const FVector> PositionView(Positions);
	const TArrayView<const float> MaskView(Masks);
	FDNACalibSetVertexPositionsCommand Command(
		Mesh, PositionView, MaskView, EDNACalibVectorOperation::Interpolate);
	Command.Run(&Calib);

	OutLayerNote = FString::Printf(
		TEXT("EDIT touched GEOMETRY (vertex positions, %d weighted of %d, ")
		TEXT("%d at full weight, feather band %.3f cm, smoothstep) of mesh ")
		TEXT("%d '%s'; WROTE EDNADataLayer::All to %s"),
		Selected.Num(), static_cast<int32>(VertexCount), CoreCount,
		FeatherBandCm, MeshIndex, *Reader->GetMeshName(Mesh), *OutDNAPath);

	SaveDNAToFile(&Calib, EDNADataLayer::All, OutDNAPath);
	if (!FPaths::FileExists(OutDNAPath))
	{
		OutError = FString::Printf(
			TEXT("SaveDNAToFile returned but %s does not exist."),
			*OutDNAPath);
		return;
	}

	// SELF-VERIFY FROM DISK. "The call returned" is not evidence that the
	// bytes say what you think, and checking only the SELECTED vertices
	// would not establish that the other tens of thousands were carried
	// through rather than defaulted.
	TSharedPtr<IDNAReader> Back = LoadDNAFromFile(OutDNAPath);
	if (!Back.IsValid())
	{
		OutError = FString::Printf(
			TEXT("Wrote %s but it did not parse back as DNA."), *OutDNAPath);
		return;
	}
	if (Back->GetVertexPositionCount(Mesh) != VertexCount)
	{
		OutError = FString::Printf(
			TEXT("Read-back vertex count %d, wrote %d."),
			static_cast<int32>(Back->GetVertexPositionCount(Mesh)),
			static_cast<int32>(VertexCount));
		return;
	}
	// THIS IS WHERE THE MASK SEMANTIC IS PROVEN, NOT ASSUMED. The expectation
	// is original + Delta * weight, which holds only if Interpolate lerps
	// between the original and the offered position by the mask. A different
	// semantic produces a different shape and is caught here rather than
	// shipped as a quietly wrong edit.
	const double Tol = 1e-3;
	for (int32 Index : Selected)
	{
		const FVector Got = Back->GetVertexPosition(
			Mesh, static_cast<uint32>(Index));
		const double W = static_cast<double>(Masks[Index]);
		const FVector Want = Original[Index] + Delta * W;
		if (FMath::Abs(Got.X - Want.X) > Tol ||
			FMath::Abs(Got.Y - Want.Y) > Tol ||
			FMath::Abs(Got.Z - Want.Z) > Tol)
		{
			OutError = FString::Printf(
				TEXT("Read-back disagrees at WEIGHTED vertex %d (w=%.4f): ")
				TEXT("expected original + Delta*w = (%.5f, %.5f, %.5f), file ")
				TEXT("says (%.5f, %.5f, %.5f). The mask semantic is not the ")
				TEXT("lerp this assumes."),
				Index, W, Want.X, Want.Y, Want.Z, Got.X, Got.Y, Got.Z);
			return;
		}
	}
	int32 Checked = 0;
	TSet<int32> SelectedSet(Selected);
	for (uint32 i = 0; i < VertexCount && Checked < 512; ++i)
	{
		if (SelectedSet.Contains(static_cast<int32>(i)))
		{
			continue;
		}
		++Checked;
		const FVector Got = Back->GetVertexPosition(Mesh, i);
		const FVector Want = Original[i];
		if (FMath::Abs(Got.X - Want.X) > Tol ||
			FMath::Abs(Got.Y - Want.Y) > Tol ||
			FMath::Abs(Got.Z - Want.Z) > Tol)
		{
			OutError = FString::Printf(
				TEXT("ZERO-WEIGHT vertex %d moved: source (%.5f, %.5f, %.5f), ")
				TEXT("file says (%.5f, %.5f, %.5f). Either the untouched ")
				TEXT("vertices were not carried through, or the mask is not ")
				TEXT("being honoured."),
				static_cast<int32>(i), Want.X, Want.Y, Want.Z,
				Got.X, Got.Y, Got.Z);
			return;
		}
	}
	OutLayerNote += FString::Printf(
		TEXT("; self-verified %d weighted (against original + Delta*w) and ")
		TEXT("%d zero-weight vertices"),
		Selected.Num(), Checked);

	bOutSuccess = true;
}

void ULandscapeLabTools::BuildGroomBindingForMesh(
	UGroomBindingAsset* SourceBinding,
	USkeletalMesh* TargetMesh,
	const FString& DestPackagePath,
	const FString& DestGroomPath,
	FString& OutBindingPath,
	FString& OutGroomPath,
	bool& bOutSuccess,
	FString& OutError,
	UGroomAsset* OverrideGroom)
{
	bOutSuccess = false;
	OutBindingPath.Reset();
	OutGroomPath.Reset();
	OutError.Reset();

	if (!SourceBinding)
	{
		OutError = TEXT("SourceBinding is null. This wants an ALREADY-BUILT binding "
			"to duplicate -- normally the vendor one shipped with the wardrobe item. "
			"Creating one from scratch is what does not work.");
		return;
	}
	if (!TargetMesh)
	{
		OutError = TEXT("TargetMesh is null.");
		return;
	}
	// THE GROOM TO DEFORM: the override when given, otherwise the source
	// binding's own. A custom groom imported from an .abc has no binding of
	// its own, so the vendor binding is borrowed purely for its retarget and
	// the cargo is swapped here.
	UGroomAsset* SourceGroom = OverrideGroom ? OverrideGroom : SourceBinding->GetGroom();
	if (!SourceGroom)
	{
		OutError = TEXT("No groom to bind: OverrideGroom is null and SourceBinding "
			"has no groom of its own.");
		return;
	}
	if (!DestPackagePath.StartsWith(TEXT("/Game/")) || !DestGroomPath.StartsWith(TEXT("/Game/")))
	{
		// A groom outside project content was the first wrong theory of this
		// whole investigation; refuse the shape of it outright.
		OutError = TEXT("Both destination paths must be under /Game/.");
		return;
	}

	// ---- the binding: a duplicate of an ALREADY-BUILT one, retargeted -----
	UPackage* BindPackage = CreatePackage(*DestPackagePath);
	UPackage* GroomPackage = CreatePackage(*DestGroomPath);
	if (!BindPackage || !GroomPackage)
	{
		OutError = TEXT("CreatePackage failed.");
		return;
	}
	BindPackage->FullyLoad();
	GroomPackage->FullyLoad();

	UGroomBindingAsset* NewBinding = DuplicateObject<UGroomBindingAsset>(
		SourceBinding, BindPackage, FName(*FPackageName::GetShortName(DestPackagePath)));
	UGroomAsset* NewGroom = DuplicateObject<UGroomAsset>(
		SourceGroom, GroomPackage, FName(*FPackageName::GetShortName(DestGroomPath)));
	if (!NewBinding || !NewGroom)
	{
		OutError = TEXT("DuplicateObject returned null.");
		return;
	}
	NewBinding->SetFlags(RF_Public | RF_Standalone);
	NewGroom->SetFlags(RF_Public | RF_Standalone);
	NewGroom->ConditionalPostLoad();

	// Retarget BEFORE the bake: the deformer reads the binding's target mesh.
	NewBinding->SetTargetSkeletalMesh(TargetMesh);
	TargetMesh->Build();

	// ---- STRIP DECIMATION BEFORE THE BAKE --------------------------------
	// The pipeline's own comment: "The RBF deformer doesn't support decimation
	// in the interpolation data (decimation in FHairLODSettings doesn't affect
	// it), so we need to remove any decimation first and then restore it
	// afterwards." Skipping this produced a groom that drew 3,353 px -- almost
	// nothing, though what there was sat correctly on the crown, which is what
	// pointed here.
	TArray<FHairGroupsInterpolation>& InterpData = NewGroom->GetHairGroupsInterpolation();
	const TArray<FHairGroupsInterpolation> OriginalInterpData = InterpData;
	bool bHadDecimation = false;
	for (FHairGroupsInterpolation& Interp : InterpData)
	{
		if (Interp.DecimationSettings.CurveDecimation < 1.0f
			|| Interp.DecimationSettings.VertexDecimation < 1.0f)
		{
			Interp.DecimationSettings.CurveDecimation = 1.0f;
			Interp.DecimationSettings.VertexDecimation = 1.0f;
			bHadDecimation = true;
		}
	}
	// POINT THE BINDING AT THE DUPLICATE BEFORE THE BAKE, ALWAYS.
	// The pipeline only does this inside its decimation branch, and following
	// that literally splits the behaviour: grooms WITH decimation baked
	// correctly (215,647 px, crown 35%) while grooms WITHOUT it produced
	// 3,4xx px at crown 42% -- hair in the right place and almost none of it.
	// The difference is that the working branch passes the SAME object as
	// input and output, so the deformation is applied in place against a
	// binding that already points at it. Doing it unconditionally makes every
	// groom take the path that was measured to work.
	NewBinding->SetGroom(NewGroom);
	if (bHadDecimation)
	{
		FPropertyChangedEvent DecimationEvent(
			FHairDecimationSettings::StaticStruct()->FindPropertyByName(
				GET_MEMBER_NAME_CHECKED(FHairDecimationSettings, CurveDecimation)));
		NewGroom->PostEditChangeProperty(DecimationEvent);
	}

	// ---- the step that actually moves the hair ---------------------------
	// Without this the binding builds, the editor survives, and the render is
	// a bald crown at crown 1% -- measured. The vendor groom is shaped for the
	// archetype head and only this bake moves it onto ours.
	FGroomRBFDeformer().GetRBFDeformedGroomAsset(
		NewBinding->GetGroom(),   // == NewGroom; in-place, the measured-good path
		NewBinding,             // the retargeted binding supplies the transform
		nullptr,                // no mask modulation, same as the pipeline
		0.0f,
		NewGroom,               // out: the deformed copy
		nullptr,                // no target platform
		true);                  // build static meshes; we are on the game thread

	if (bHadDecimation)
	{
		InterpData = OriginalInterpData;
		FPropertyChangedEvent RestoreEvent(
			FHairDecimationSettings::StaticStruct()->FindPropertyByName(
				GET_MEMBER_NAME_CHECKED(FHairDecimationSettings, CurveDecimation)));
		NewGroom->PostEditChangeProperty(RestoreEvent);
	}

	// CORRECTED 2026-08-20 -- THIS COMMENT USED TO CLAIM THE OPPOSITE.
	// It read "the cards and mesh descriptions are duplicated by the pipeline
	// too, so the deformed groom does not share static meshes with the vendor
	// asset." MEASURED FALSE: after a catalogue run,
	// get_dirty_content_packages() returns 48 packages and ALL 48 are vendor
	// content under /MetaHumanCharacter/Optional -- the groom's own
	// <Style>_CardsMesh_Group0_LOD* and <Style>_Helmet_LOD* static meshes.
	// So DuplicateObject does NOT deep-copy them: the duplicate references
	// the vendor's, and this PostEditChangeProperty rebuilds them in place.
	//
	// CONSEQUENCE, and it is why this is written out in full: those packages
	// live in Program Files, outside both roots. They are dirty in MEMORY and
	// clean on disk (all 1387 vendor groom uassets still carry their
	// 2026-08-15 install mtime, checked by directory listing), so nothing is
	// damaged -- but any Save All, autosave or save-on-quit would write engine
	// plugin content and break both the never-edit-vendor-content floor and
	// standing rule 1. DISCARD ON EVERY CLOSE while this call is here.
	FPropertyChangedEvent CardsEvent(
		UGroomAsset::StaticClass()->FindPropertyByName(
			UGroomAsset::GetHairGroupsCardsMemberName()));
	NewGroom->PostEditChangeProperty(CardsEvent);

	NewBinding->SetGroom(NewGroom);
	NewBinding->SetSourceSkeletalMesh(nullptr);
	NewBinding->Build();

	FAssetRegistryModule::AssetCreated(NewGroom);
	FAssetRegistryModule::AssetCreated(NewBinding);
	GroomPackage->MarkPackageDirty();
	BindPackage->MarkPackageDirty();

	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;

	const FString GroomFile = FPackageName::LongPackageNameToFilename(
		DestGroomPath, FPackageName::GetAssetPackageExtension());
	const FString BindFile = FPackageName::LongPackageNameToFilename(
		DestPackagePath, FPackageName::GetAssetPackageExtension());
	if (!UPackage::SavePackage(GroomPackage, NewGroom, *GroomFile, SaveArgs))
	{
		OutError = TEXT("SavePackage failed for the deformed groom.");
		return;
	}
	if (!UPackage::SavePackage(BindPackage, NewBinding, *BindFile, SaveArgs))
	{
		OutError = TEXT("SavePackage failed for the binding.");
		return;
	}

	OutBindingPath = DestPackagePath;
	OutGroomPath = DestGroomPath;
	bOutSuccess = true;
}

void ULandscapeLabTools::BuildFreshGroomBinding(
	UGroomAsset* Groom,
	USkeletalMesh* SourceMesh,
	USkeletalMesh* TargetMesh,
	const FString& DestPackagePath,
	const FString& DestGroomPath,
	FString& OutBindingPath,
	FString& OutGroomPath,
	bool& bOutSuccess,
	FString& OutError,
	int32 NumInterpolationPoints,
	int32 MatchingSection)
{
	OutGroomPath.Reset();
	bOutSuccess = false;
	OutBindingPath.Reset();
	OutError.Reset();

	if (!Groom)
	{
		OutError = TEXT("Groom is null.");
		return;
	}
	if (!TargetMesh)
	{
		OutError = TEXT("TargetMesh is null.");
		return;
	}
	if (!DestPackagePath.StartsWith(TEXT("/Game/")))
	{
		OutError = TEXT("Destination must be under /Game/.");
		return;
	}

	// SOURCE DEFAULTS TO TARGET, AND THAT IS A MEANINGFUL CHOICE.
	// A binding transfers a groom from the mesh it was AUTHORED on to the mesh
	// it must sit on. When the groom was authored directly on the target's own
	// topology there is nothing to transfer, and source == target makes the
	// binding an identity. Passing null says "authored here" rather than
	// silently reusing whatever the caller had lying around.
	USkeletalMesh* EffectiveSource = SourceMesh ? SourceMesh : TargetMesh;

	// Both meshes must be built before the binding can read their geometry.
	EffectiveSource->Build();
	if (TargetMesh != EffectiveSource)
	{
		TargetMesh->Build();
	}

	UPackage* BindPackage = CreatePackage(*DestPackagePath);
	if (!BindPackage)
	{
		OutError = TEXT("CreatePackage failed.");
		return;
	}
	BindPackage->FullyLoad();

	// The ENGINE'S OWN CREATOR, not a hand-rolled NewObject. It sets the
	// binding up the way the engine expects, which is the whole point of
	// preferring it: this recipe's history is a sequence of hand-assembled
	// approximations that each looked right and rendered wrong.
	UGroomBindingAsset* NewBinding = FHairStrandsCore::CreateGroomBindingAsset(
		EGroomBindingMeshType::SkeletalMesh,
		DestPackagePath,
		BindPackage,
		Groom,
		EffectiveSource,
		TargetMesh,
		NumInterpolationPoints,
		MatchingSection);

	if (!NewBinding)
	{
		OutError = TEXT("CreateGroomBindingAsset returned null.");
		return;
	}
	NewBinding->SetFlags(RF_Public | RF_Standalone);

	// ~~NO RBF BAKE HERE, DELIBERATELY.~~ STRUCK 2026-08-21 -- THIS COMMENT
	// WAS FALSE FOR AS LONG AS THE BAKE BLOCK BELOW HAS EXISTED, and it sat
	// forty lines above a block whose own heading says it "overturns the plan
	// this function was written to". Two claims in one function asserting
	// opposite things, and nothing re-checked either (non-negotiable 25).
	// Kept struck rather than deleted because it records what the function
	// was designed to do before measurement changed it.
	// The live rule is at the bake block: bake only when there is a transfer
	// to bake.
	NewBinding->Build();

	// BUILD() IS ASYNCHRONOUS AND RETURNING IS NOT FINISHING.
	// Measured: without this wait the call returned in 0.01 s for a
	// 31,267-strand groom -- twice, and with two different source meshes
	// producing pixel-identical renders. That last part is the tell: a
	// result that does not move when its input does is a result that was
	// never computed. The package was then saved before the compile
	// finished, so the binding carried no transfer data at all and the
	// groom rendered in its raw authored position, on the collarbone.
	//
	// R-GROOMBIND3 never hit this because it bakes the deformation into the
	// GROOM, so its placement does not depend on the binding's async build.
	// This path does, which is exactly why it needs the wait and that one
	// does not.
	FGroomBindingCompilingManager::Get().FinishCompilation({ NewBinding });

	// ---- AND NOW BAKE IT INTO THE GROOM, BECAUSE THE BINDING ALONE DOES
	// ---- NOT MOVE STRANDS IN THIS SETUP.
	// Measured, and it overturns the plan this function was written to:
	// three bindings -- identity source, real source async, real source
	// synchronous -- produced the SAME PICTURE. Pairwise whole-frame
	// differences were 0.2% between two of them and 6.3% to the third, and
	// 6.3% sits inside this scene's known frame-to-frame instability band,
	// so none of it is signal. A groom whose placement does not move when
	// its binding changes is a groom whose placement the binding is not
	// driving.
	//
	// That is exactly why R-GROOMBIND3 bakes. The difference here is WHICH
	// binding does the baking: that recipe borrows a vendor binding carrying
	// a foreign groom's correspondence, and this one bakes through a binding
	// built for this groom's own roots against the head it was authored on.
	// Correct correspondence, and the mechanism that actually moves hair.
	if (!DestGroomPath.IsEmpty())
	{
		if (!DestGroomPath.StartsWith(TEXT("/Game/")))
		{
			OutError = TEXT("DestGroomPath must be under /Game/.");
			return;
		}
		UPackage* GroomPackage = CreatePackage(*DestGroomPath);
		if (!GroomPackage)
		{
			OutError = TEXT("CreatePackage failed for the deformed groom.");
			return;
		}
		GroomPackage->FullyLoad();
		UGroomAsset* NewGroom = DuplicateObject<UGroomAsset>(
			Groom, GroomPackage, FName(*FPackageName::GetShortName(DestGroomPath)));
		if (!NewGroom)
		{
			OutError = TEXT("DuplicateObject returned null for the groom.");
			return;
		}
		NewGroom->SetFlags(RF_Public | RF_Standalone);
		NewGroom->ConditionalPostLoad();

		// The RBF deformer does not support decimation in the interpolation
		// data, so strip it around the bake and restore afterwards. Skipping
		// this produced hair in the right place and almost none of it when
		// R-GROOMBIND3 was built; the same applies here.
		TArray<FHairGroupsInterpolation>& InterpData = NewGroom->GetHairGroupsInterpolation();
		const TArray<FHairGroupsInterpolation> OriginalInterpData = InterpData;
		bool bHadDecimation = false;
		for (FHairGroupsInterpolation& Interp : InterpData)
		{
			if (Interp.DecimationSettings.CurveDecimation < 1.0f
				|| Interp.DecimationSettings.VertexDecimation < 1.0f)
			{
				Interp.DecimationSettings.CurveDecimation = 1.0f;
				Interp.DecimationSettings.VertexDecimation = 1.0f;
				bHadDecimation = true;
			}
		}
		NewBinding->SetGroom(NewGroom);
		if (bHadDecimation)
		{
			FPropertyChangedEvent DecimationEvent(
				FHairDecimationSettings::StaticStruct()->FindPropertyByName(
					GET_MEMBER_NAME_CHECKED(FHairDecimationSettings, CurveDecimation)));
			NewGroom->PostEditChangeProperty(DecimationEvent);
		}

		// ---- BAKE ONLY WHEN THERE IS A TRANSFER TO BAKE ----------------
		// THIS CALL KILLED THE EDITOR ON 2026-08-21:
		//   Assertion failed: RootDatas[GroupIndex].MeshPositions
		//     .IsValidIndex(MeshLODIndex)
		//   GroomRBFDeformer.cpp:740
		// on a 50,400-curve groom authored on the target's own head, bound
		// with source == target. An engine check() is a hard crash, so a
		// precondition we cannot verify is one we must not walk into.
		//
		// AND FOR THIS INPUT THE STEP IS A NO-OP BY CONSTRUCTION. An RBF
		// deformation carries strands from the mesh the groom was AUTHORED
		// on to the mesh it must SIT on. When those are the same mesh the
		// transfer is the identity; there is nothing to move. The block
		// below was added after measuring that three bindings produced the
		// same picture, but that was measured on a groom authored somewhere
		// else -- it says the bake is what moves a TRANSFERRED groom, not
		// that a groom already in the right place needs moving.
		//
		// So: bake when the meshes differ, skip when they do not, and LOG
		// which happened, rather than leaving the caller to infer it from a
		// groom that may or may not have been deformed.
		const bool bNeedsTransfer = (EffectiveSource != TargetMesh);
		UE_LOG(LogLandscapeLab, Display,
			TEXT("BuildFreshGroomBinding: RBF bake %s (source %s target)."),
			bNeedsTransfer ? TEXT("RUN") : TEXT("SKIPPED"),
			bNeedsTransfer ? TEXT("differs from") : TEXT("IS the"));
		if (bNeedsTransfer)
		{
			FGroomRBFDeformer().GetRBFDeformedGroomAsset(
				NewBinding->GetGroom(), NewBinding, nullptr, 0.0f,
				NewGroom, nullptr, true);
		}

		if (bHadDecimation)
		{
			InterpData = OriginalInterpData;
			FPropertyChangedEvent RestoreEvent(
				FHairDecimationSettings::StaticStruct()->FindPropertyByName(
					GET_MEMBER_NAME_CHECKED(FHairDecimationSettings, CurveDecimation)));
			NewGroom->PostEditChangeProperty(RestoreEvent);
		}

		NewBinding->SetGroom(NewGroom);
		NewBinding->Build();
		FGroomBindingCompilingManager::Get().FinishCompilation({ NewBinding });

		FAssetRegistryModule::AssetCreated(NewGroom);
		GroomPackage->MarkPackageDirty();
		FSavePackageArgs GroomSaveArgs;
		GroomSaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
		GroomSaveArgs.SaveFlags = SAVE_NoError;
		const FString GroomFile = FPackageName::LongPackageNameToFilename(
			DestGroomPath, FPackageName::GetAssetPackageExtension());
		if (!UPackage::SavePackage(GroomPackage, NewGroom, *GroomFile, GroomSaveArgs))
		{
			OutError = TEXT("SavePackage failed for the deformed groom.");
			return;
		}
		OutGroomPath = DestGroomPath;
	}

	// The component REFUSES a binding that still names a source mesh --
	// measured: set_binding_asset read back null until this was cleared, and
	// R-GROOMBIND3 ends the same way. The computed transfer survives; only
	// the pointer goes.
	NewBinding->SetSourceSkeletalMesh(nullptr);

	FAssetRegistryModule::AssetCreated(NewBinding);
	BindPackage->MarkPackageDirty();

	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	SaveArgs.SaveFlags = SAVE_NoError;
	const FString BindFile = FPackageName::LongPackageNameToFilename(
		DestPackagePath, FPackageName::GetAssetPackageExtension());
	if (!UPackage::SavePackage(BindPackage, NewBinding, *BindFile, SaveArgs))
	{
		OutError = TEXT("SavePackage failed for the binding.");
		return;
	}

	OutBindingPath = DestPackagePath;
	bOutSuccess = true;
}
