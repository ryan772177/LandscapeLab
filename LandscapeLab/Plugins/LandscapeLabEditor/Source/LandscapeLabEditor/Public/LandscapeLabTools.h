// Copyright Ryan B. LandscapeLab.
//
// WHY THIS EXISTS
//
// UE 5.8 declares the three operations below LANDSCAPE_API and never marks any
// of them UFUNCTION, so none of them is reachable from Python:
//
//   ALandscapeProxy::Import          LandscapeProxy.h:1416
//   ULandscapeSubsystem::BuildNanite LandscapeSubsystem.h:148
//   ULandscapeSubsystem::ChangeGridSize LandscapeSubsystem.h:153
//
// There is no ULandscapeEditorSubsystem to route around it. This module is the
// smallest thing that makes a landscape creatable and importable from a script.
//
// The reference implementation these wrappers follow is the engine's own
// New Landscape button:
//   Engine/Source/Editor/LandscapeEditor/Private/
//     LandscapeEditorDetailCustomization_NewLandscape.cpp:1150-1290
// It is the only call site of ALandscapeProxy::Import in the editor, and the
// ordering below (spawn -> set material -> Import -> UpdateLayerInfoMap ->
// ChangeGridSize) is taken from it rather than invented.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "LandscapeLabTools.generated.h"

class ALandscape;
class ALandscapeProxy;
class UMaterialInterface;
class USkeletalMesh;
class UGroomBindingAsset;

UCLASS()
class LANDSCAPELABEDITOR_API ULandscapeLabTools : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Spawn an ALandscape in the editor world and import a heightmap into it.
	 *
	 * REFUSES, rather than adjusting anything, when:
	 *   - QuadsPerSection is not one of 7/15/31/63/127/255
	 *   - SectionsPerComponent is not 1 or 2  (the engine allows only these two;
	 *     the documentation's "1 or 4" is wrong and is on this project's
	 *     casualty list)
	 *   - either component count is < 1
	 *   - the heightmap file's resolution is not exactly
	 *     ComponentCount * SectionsPerComponent * QuadsPerSection + 1
	 *
	 * That last one is the load-bearing gate. The engine will happily resample or
	 * expand a mismatched heightmap; this function will not, because a silently
	 * resampled terrain is indistinguishable from a correct one until every
	 * downstream placement has already been computed against it.
	 *
	 * @param HeightmapPath        Absolute path to a 16-bit heightmap (PNG/RAW/R16).
	 * @param Location             Actor location in cm. See bCenterOnLocation.
	 * @param Rotation             Actor rotation.
	 * @param Scale                Actor scale. X/Y are cm per quad; Z is the
	 *                             landscape Z scale (100 == 512 m of range).
	 * @param SectionsPerComponent 1 or 2.
	 * @param QuadsPerSection      7, 15, 31, 63, 127 or 255.
	 * @param ComponentCountX      Components along X.
	 * @param ComponentCountY      Components along Y.
	 * @param LandscapeMaterial    May be null; the landscape then renders the
	 *                             engine default material.
	 * @param WorldPartitionGridSize Components per streaming proxy along each
	 *                             axis. 0 leaves the landscape unsplit. Only
	 *                             applied when the world is grid based.
	 * @param ActorLabel           Editor label. Empty means the engine default.
	 * @param bFlipYAxis           Flip the heightmap's Y on read.
	 * @param bCenterOnLocation    true (the New Landscape button's behaviour)
	 *                             centres the landscape on Location. false puts
	 *                             the actor origin at Location.
	 * @param OutError             Empty on success; the reason on failure.
	 * @return                     The landscape, or null on any refusal.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab",
		meta = (AdvancedDisplay = "9"))
	static ALandscape* CreateLandscapeFromHeightmap(
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
		FString& OutError);

	/**
	 * Read a heightmap file's resolution without importing it. Use this to pick
	 * or check a component layout before committing to a create.
	 *
	 * bOutSuccess is false when the file could not be read, and the dimensions
	 * are left at 0. A zero produced because the file could not be opened is
	 * reported through bOutSuccess and OutError, never returned as "0 x 0".
	 *
	 * WHY THIS RETURNS void AND NOT bool -- and it applies to every function
	 * in this class. Measured against the running 5.8 editor, a UFUNCTION that
	 * returns bool AND has out-params does not expose the bool to Python at
	 * all: the generated signature is
	 *
	 *     get_heightmap_resolution(path) -> (out_width, out_height, out_error) or None
	 *
	 * The bool is consumed as a success flag and the whole tuple collapses to
	 * None when it is false -- so OutError, the one thing worth having on a
	 * failure, becomes unreachable exactly when it is needed. An explicit
	 * bOutSuccess keeps the reason readable. The reflected Python surface is
	 * the contract, not the C++ header.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	static void GetHeightmapResolution(
		const FString& HeightmapPath,
		int32& OutWidth,
		int32& OutHeight,
		bool& bOutSuccess,
		FString& OutError);

	/**
	 * Build the Nanite representation of every landscape proxy in the editor
	 * world. Wraps ULandscapeSubsystem::BuildNanite.
	 *
	 * This is the sanctioned route. The workaround currently recorded in
	 * RECIPES -- setting landscape.Nanite.LiveRebuildOnModification and poking
	 * the landscape -- triggers a rebuild as a side effect of modification and
	 * cannot report whether it finished.
	 *
	 * @param bForceRebuild Rebuild even where the engine thinks it is current.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	static void BuildLandscapeNanite(bool bForceRebuild, bool& bOutSuccess, FString& OutError);

	/**
	 * Build the Nanite representation of EXACTLY the proxies handed in, and no
	 * others. This is the batched form of BuildLandscapeNanite.
	 *
	 * WHY THIS EXISTS -- and it is a memory bound, not a convenience.
	 * ULandscapeSubsystem::BuildNanite dispatches UpdateNaniteRepresentationAsync
	 * for every proxy in one loop and only then blocks on
	 * FinishAllNaniteBuildsInFlightNow (LandscapeSubsystem.cpp:1159-1181), so
	 * every proxy's mesh build is in flight at once. On this project's 8129
	 * landscape that is 256 simultaneous static-mesh builds; the editor was
	 * OOM-killed at PeakUsedVirtual 115.47 GiB.
	 *
	 * THE ENGINE'S OWN THROTTLE FOR THIS IS DEAD CODE IN 5.8, so do not reach for
	 * it instead: landscape.Nanite.MaxSimultaneousMultithreadBuilds (-1 =
	 * unlimited, LandscapeSubsystem.cpp:92-97) is read only by
	 * ULandscapeSubsystem::WaitLaunchNaniteBuild (:1583), whose single call site
	 * in the whole module is commented out at LandscapeNaniteComponent.cpp:273
	 * -- "TODO [chris.tchou]: this can deadlock, any waits should be done outside
	 * of async tasks". Setting that cvar changes nothing. Bounding the SUBMITTED
	 * SET is the only lever the engine leaves.
	 *
	 * REFUSES, before touching anything, when:
	 *   - the array is empty. An empty TArrayView means BUILD EVERY REGISTERED
	 *     PROXY to the subsystem (LandscapeSubsystem.cpp:1124-1133). A batch
	 *     function that quietly expanded an empty batch into the 9-hour monolith
	 *     would be the exact catastrophic value this parameter exists to avoid,
	 *     so the empty case is refused rather than defaulted.
	 *   - any entry is null. A stale Python reference must not read as "fewer
	 *     proxies than I asked for" -- the engine silently drops nulls at :1156.
	 *   - any entry is an ALandscape that owns streaming proxies. The subsystem
	 *     expands such an actor to ALL of its streaming proxies (:1140-1147), so
	 *     one parent actor in a batch of eight silently becomes a batch of 256.
	 *     The refusal names how many it would have expanded to.
	 *   - any entry belongs to a different world than the editor world.
	 *   - any entry has Nanite DISABLED. UpdateNaniteRepresentationAsync does
	 *     nothing at all unless IsNaniteEnabled() (Landscape.cpp:465), so such a
	 *     proxy is a silent no-op that returns success. Set enable_nanite first.
	 *
	 * @param ProxiesToBuild        The batch. Streaming proxies, not the parent.
	 * @param bForceRebuild         Rebuild even where the engine thinks the mesh
	 *                              is current. Leave FALSE to make the operation
	 *                              resumable: the subsystem drops proxies whose
	 *                              IsNaniteMeshUpToDate() is true (:1156), so a
	 *                              re-run after a crash skips what already built.
	 * @param OutProxiesSubmitted   How many proxies passed validation and were
	 *                              handed to the subsystem.
	 * @param OutProxiesAlreadyUpToDate  How many of those the engine will skip,
	 *                              measured HERE with IsNaniteMeshUpToDate()
	 *                              before the call. Reported so the caller can
	 *                              tell "this batch did nothing because it was
	 *                              already built" from "this batch did nothing".
	 *                              THIS IS NOT A PROOF THAT A MESH EXISTS.
	 *                              IsNaniteMeshUpToDate() also returns true for a
	 *                              proxy with Nanite disabled, and for one with no
	 *                              landscape components at all (Landscape.cpp:443-456)
	 *                              -- which is why the parent ALandscape of a grid
	 *                              world reports up to date while owning no mesh.
	 *                              The first of those cases is refused above; the
	 *                              caller must still confirm a built mesh with a
	 *                              different instrument (a LandscapeNaniteComponent
	 *                              holding a static mesh), per non-negotiable 8.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	static void BuildLandscapeNaniteForProxies(
		const TArray<ALandscapeProxy*>& ProxiesToBuild,
		bool bForceRebuild,
		int32& OutProxiesSubmitted,
		int32& OutProxiesAlreadyUpToDate,
		bool& bOutSuccess,
		FString& OutError);

	/**
	 * Load EVERY World Partition region in the editor world, so a measurement
	 * taken afterwards is about the whole level rather than about whatever
	 * happened to be streamed in.
	 *
	 * WHY THIS IS A CORRECTNESS TOOL AND NOT A CONVENIENCE.
	 * A frame-cost capture on this project's 8129 landscape read GPUTime
	 * 2.92 ms and looked like a decisive GO for 1 m/vertex. Four of 256
	 * streaming proxies were resident: the number described 1.6% of the
	 * landscape. Non-negotiable 7 -- "verify an invariant on complete state" --
	 * was written after a count taken with regions unloaded became a gate that
	 * inverted itself. Nothing about an unloaded world announces itself.
	 *
	 * This is exactly what the editor's own World Partition "Load Region"
	 * button does over the whole world bounds:
	 *   SWorldPartitionEditorGrid2D.cpp:702-710 (region from selection)
	 *   FileHelpers.cpp:1250-1256            (whole GetRuntimeWorldBounds)
	 * both of which build an FLoaderAdapterShape, SetUserCreated(true), Load().
	 *
	 * The Z extent is forced to +/-HALF_WORLD_MAX rather than taken from the
	 * world bounds, matching the region tool: the query is spatial, and a
	 * Z range derived from current contents would silently exclude anything
	 * outside it.
	 *
	 * MEMORY. This is the whole point and also the hazard -- every actor in
	 * every region is resident afterwards. Log free RAM before calling it.
	 *
	 * @param bOutSuccess false with a reason if the world is not partitioned,
	 *        has no valid bounds, or the adapter could not be created.
	 * @param OutBoundsMin/OutBoundsMax the XY box actually loaded, so the
	 *        caller can report WHAT was loaded rather than assert that it was.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	static void LoadAllWorldPartitionRegions(
		bool& bOutSuccess,
		FVector& OutBoundsMin,
		FVector& OutBoundsMax,
		FString& OutError);

	/**
	 * Split (or re-split) a landscape into World Partition streaming proxies.
	 * Wraps ULandscapeSubsystem::ChangeGridSize.
	 *
	 * @param NewGridSizeInComponents Components per proxy along each axis. The
	 *        proxy count is (ComponentCountX / N) * (ComponentCountY / N).
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	static void ChangeLandscapeGridSize(
		ALandscape* Landscape,
		int32 NewGridSizeInComponents,
		bool& bOutSuccess,
		FString& OutError);

	// =====================================================================
	// MetaHuman DNA — neutral joint translations          (added 2026-08-17)
	// =====================================================================
	//
	// WHY THESE EXIST. Measured on the running 5.8 editor by
	// scripts/hero_face/likeness/env_check.py: the reflected Python surface
	// reaches a DNA READER but never the JOINTS.
	//
	//   DNA           meta_data, rig_logic_configuration    -- that is all
	//   EvaluateRig   set_rig_dna_from_asset(DNA) -> true,
	//                 evaluate_raw_controls -> VERTICES (24,049 at LOD 0)
	//
	// and the only reflected FACE write is
	// MetaHumanCharacterEditorSubsystem::import_from_face_dna, which takes a
	// whole file. There is no reflected face joint writer -- note that
	// set_body_joints exists for the BODY with no face counterpart, which
	// reads like an omission rather than a prohibition.
	//
	// The engine's own DNACalib does have one, and it speaks DNA 2.5
	// natively. (The public EpicGames/MetaHuman-DNA-Calibration bindings
	// read only 2.1 and hard-fail on this character's file, so they are not
	// an option and were already tried.)
	//
	// EVERY NAME BELOW WAS READ FROM A HEADER, NOT REMEMBERED:
	//   IDNAReader::GetJointCount                 DNAReader.h:95
	//   IDNAReader::GetJointName                  DNAReader.h:96
	//   IDNAReader::GetNeutralJointTranslation    DNAReader.h:115
	//   LoadDNAFromFile / SaveDNAToFile           DNAUtils.h
	//   FDNACalibDNAReader(IDNAReader*)           DNACalibDNAReader.h
	//   FDNACalibSetNeutralJointTranslationsCommand
	//       Commands/DNACalibSetNeutralJointTranslationsCommand.h
	//
	// AND ONE OWNERSHIP TRAP, settled by reading the .cpp rather than the
	// header: FDNACalibDNAReader declares `TUniquePtr<IDNAReader> ReaderPtr`,
	// which reads as "takes ownership of Source". It does not.
	// DNACalibDNAReader.cpp:10-12 calls Source->Unwrap() and creates its OWN
	// dnac::DNACalibDNAReader copy, so the caller's TSharedPtr keeps
	// ownership and there is no double free. Inferring from the header would
	// have crashed the editor.
	//
	// THESE ARE FILE-TO-FILE, DELIBERATELY. Neither one touches the live
	// 138 MB character asset or the Face skeletal mesh. The round trip is
	// export_dna (reflected) -> these -> import_from_face_dna (reflected),
	// so the only thing this plugin owns is the DNA transform, and every
	// mutation of project content still goes through UE's own tooling.

	/**
	 * Read every neutral joint translation out of a .dna file.
	 *
	 * This is also the answer to env_check's criterion (c): OutJointCount is
	 * the DNA's own joint count, which is NOT the Face skeleton's bone count
	 * (measured 870 against 875 -- a DNA joint list and a USkeleton bone tree
	 * are different objects, and the difference is not a discrepancy).
	 *
	 * @param DNAPath          Absolute path to a .dna file.
	 * @param OutJointNames    One entry per joint, in DNA index order.
	 * @param OutTranslations  Neutral translation per joint, centimetres.
	 * @param OutJointCount    Joint count as the DNA reports it.
	 * @param OutFormat        e.g. "2.5 (gen 2, ver 5)", read from the file
	 *                         rather than assumed, so a format change is
	 *                         visible instead of silently mis-parsed.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|DNA")
	static void ReadDNAJoints(
		const FString& DNAPath,
		TArray<FString>& OutJointNames,
		TArray<FVector>& OutTranslations,
		int32& OutJointCount,
		FString& OutFormat,
		bool& bOutSuccess,
		FString& OutError);

	/**
	 * Write new neutral translations for SOME joints into a NEW .dna file.
	 *
	 * Reads InDNAPath, replaces the translations at JointIndices, and writes
	 * the whole DNA to OutDNAPath. DNACalib's command sets translations for
	 * EVERY joint at once, so the untouched joints are carried through from
	 * the source rather than defaulted.
	 *
	 * REFUSES, rather than doing something approximate, when:
	 *   - InDNAPath does not exist, or does not load
	 *   - OutDNAPath is the same file as InDNAPath. In-place editing of the
	 *     canonical DNA is refused outright: it is the only thing that puts
	 *     the head back after an import_whole_rig, and this project has
	 *     already lost a hero to content it could not restore.
	 *   - JointIndices and NewTranslations differ in length
	 *   - any index is outside [0, JointCount)
	 *   - any index appears twice (the last would silently win)
	 *
	 * SELF-VERIFYING. After writing, the output file is RE-LOADED from disk
	 * and every requested joint is compared against what was asked for. If
	 * any disagrees beyond 1e-4 cm, bOutSuccess is FALSE and OutError names
	 * the joint -- because "the call returned" is not evidence that the bytes
	 * on disk say what you think.
	 *
	 * @param OutLayerNote  Which DNA layer the EDIT touched, versus what was
	 *                      written. Neutral joint translations live in the
	 *                      DEFINITION layer; SaveDNAToFile writes All.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|DNA")
	static void WriteDNAJointTranslations(
		const FString& InDNAPath,
		const FString& OutDNAPath,
		const TArray<int32>& JointIndices,
		const TArray<FVector>& NewTranslations,
		int32& OutJointCount,
		FString& OutLayerNote,
		bool& bOutSuccess,
		FString& OutError);

	/**
	 * Apply a .dna to a SkeletalMesh, one stage at a time, and report what
	 * the mesh's OWN reference skeleton says before and after.
	 *
	 * WHY THE STAGES ARE SEPARATE FLAGS RATHER THAN ONE "apply" CALL.
	 * `USkelMeshDNAUtils::UpdateJoints` is documented in engine source as
	 * "Updates bind pose using joint positions from DNA"
	 * (SkelMeshDNAUtils.cpp:79). It rewrites the reference skeleton and then
	 * calls CalculateInvRefMatrices(), so the inverse-bind matrices are
	 * recomputed FROM THE NEW BIND POSE while the stored vertex positions are
	 * untouched. At the reference pose the skinning matrix is therefore
	 * NewRef * inverse(NewRef) = identity, and the skin should render exactly
	 * where it was. THE SURFACE IS MOVED BY UpdateBaseMesh, which reads the
	 * DNA's GEOMETRY layer -- a layer that a neutral-joint-translation edit
	 * does not touch at all.
	 *
	 * That is a reading of the source, not a measurement, and this project
	 * does not act on readings. Splitting the stages lets the same joint edit
	 * be rendered three ways -- joints only, joints plus geometry, and DNA
	 * attached with neither -- so the premise is settled by pixels.
	 *
	 * REFUSES rather than approximating when: the DNA file is missing or does
	 * not parse; Mesh is null; the DNA/mesh mapping cannot be built; or a
	 * probe bone name is not in the reference skeleton (a silently absent
	 * probe would report "no movement" for a bone nobody looked at).
	 *
	 * @param bUpdateJoints        UpdateJoints -- rewrites the BIND POSE
	 * @param bUpdateBaseMesh      UpdateBaseMesh -- rewrites VERTEX POSITIONS
	 *                             from the DNA geometry layer, ALL LODs
	 * @param bRebuildRenderData   full RebuildRenderData (re-chunks). When
	 *                             false and anything was updated, the cheaper
	 *                             RebuildRenderData_VertexPosition runs, which
	 *                             is what the engine's own identity path does.
	 * @param bAttachDNA           SetDNAReader -- swaps the DNA the mesh
	 *                             carries, without moving anything itself
	 * @param ProbeBoneNames       bones to read out of the mesh's reference
	 *                             skeleton. A DIFFERENT REPRESENTATION from
	 *                             the DNA file: component-space translation,
	 *                             in the mesh, after the operation.
	 * @param OutStagesRun         exactly which stages executed, in order
	 * @param ReaderSource   WHICH READER, and this is not a detail. Measured
	 *                       2026-08-17: applying the canonical exported DNA
	 *                       with the plain reader rotated the whole head --
	 *                       the DNA root reads (0, 120.0077, 4.3415) where
	 *                       the mesh's own skeleton has (0, 4.3415, 120.0077),
	 *                       an exact Y/Z swap, and UpdateJoints applies the
	 *                       value RAW.
	 *                         "file"   LoadDNAFromFile -- no swizzle
	 *                         "legacy" ReadDNAFromFile -- FLegacyDNAReader,
	 *                                  which applies the Maya->UE swizzle
	 *                                  (joints x,-y,z; rotations -y,-z,x)
	 *                         "mesh"   the DNA the mesh already CARRIES, via
	 *                                  USkelMeshDNAUtils::GetDNAReader. DNAPath
	 *                                  is ignored. This is the one that should
	 *                                  round-trip to identity if the exported
	 *                                  file is in DCC space.
	 * @param OutReaderInfo  what the reader DECLARES about itself -- axes,
	 *                       translation and rotation units, format. A DNA
	 *                       states its own coordinate system; nothing here
	 *                       needs to be inferred from a magnitude.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|DNA")
	static void ApplyDNAToSkeletalMesh(
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
		FString& OutError);

	/**
	 * Enumerate the meshes in a .dna: index, name and vertex count.
	 *
	 * Needed before any geometry edit, because "the head mesh" is an index
	 * this project must not guess. A MetaHuman face DNA carries head, teeth,
	 * eyes, saliva, lashes and more, and editing the wrong index would move
	 * something invisible in a frontal render.
	 *
	 * Returns each mesh's BOUNDING BOX in the DNA's own space as well. A
	 * region box has to be placed somewhere, and probing for the extent by
	 * trial boxes would mean writing a 54 MB DNA per probe.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|DNA")
	static void ReadDNAMeshes(
		const FString& DNAPath,
		TArray<FString>& OutMeshNames,
		TArray<int32>& OutVertexCounts,
		TArray<FVector>& OutBoundsMin,
		TArray<FVector>& OutBoundsMax,
		int32& OutMeshCount,
		FString& OutReaderInfo,
		bool& bOutSuccess,
		FString& OutError);

	/**
	 * Add a delta to every vertex of one mesh inside a declared box, and
	 * write the whole DNA out.
	 *
	 * GEOMETRY, NOT JOINTS. Measured 2026-08-17: a neutral-joint-translation
	 * edit is invisible through import_from_face_dna, because
	 * FitToFaceDna fits the parametric state to the DNA's GEOMETRY and never
	 * reads the neutral joints. Joint writes are dead weight and a false
	 * audit trail; this is the edit that can actually move a face.
	 *
	 * READ-ALL / MODIFY-SOME / WRITE-ALL. DNACalib's command replaces every
	 * position of the mesh at once, so the untouched vertices are carried
	 * through from the source rather than defaulted -- the same shape as
	 * WriteDNAJointTranslations.
	 *
	 * THE BOX IS IN THE DNA'S OWN COORDINATE SPACE, which is NOT UE's. This
	 * DNA declares axes X=Left Y=Up Z=Front (DNACommon.h:47,268, read via
	 * GetCoordinateSystem and reported in OutReaderInfo). Selecting a jaw
	 * region therefore means low Y, not low Z. Nothing here converts; the
	 * caller works in the space the file declares.
	 *
	 * REFUSES, rather than doing something approximate, when:
	 *   - InDNAPath does not exist or does not parse
	 *   - OutDNAPath is the same file as InDNAPath
	 *   - MeshIndex is outside [0, MeshCount)
	 *   - the box is degenerate on any axis (Min >= Max)
	 *   - NO VERTEX falls inside the box. An edit that reports success while
	 *     moving nothing is precisely the false audit trail this replaces.
	 *
	 * SELF-VERIFYING. The output is re-loaded from disk and every weighted
	 * vertex is checked to have moved by exactly Delta * its weight, and a
	 * sample of ZERO-WEIGHT vertices checked not to have moved at all --
	 * because "the selected ones are right" does not establish that the
	 * other 24,000 were carried through.
	 *
	 * FEATHERED, and that is not cosmetic. A hard box changes the very
	 * attenuation it is used to measure: seam vertices drag their unmoved
	 * neighbours through skinning and the fit, so a boxed number is the
	 * attenuation OF A BOXED EDIT, not of the region moving. Ruled
	 * 2026-08-17 — feather before any gain calibration.
	 *
	 * The box is the CORE (weight 1.0). FeatherBandCm extends outward from
	 * it, and the weight falls smoothstep to 0.0 at the band edge, measured
	 * by distance from the core box. Band 0 reproduces the old hard-edged
	 * behaviour and is available only so the two can be compared.
	 *
	 * HOW THE MASK IS APPLIED, and the self-verify is what proves it: every
	 * vertex is offered position = original + Delta, with a per-vertex MASK
	 * equal to its weight, under EDNACalibVectorOperation::Interpolate. If
	 * that operation lerps -- result = original + (new - original) * mask --
	 * the result is original + Delta * weight. The read-back checks exactly
	 * that expectation, so a different mask semantic FAILS LOUDLY rather
	 * than silently producing a differently-shaped edit.
	 *
	 * @param OutCoreCount  vertices at full weight
	 * @param OutSelectedCount  vertices with ANY weight above zero
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|DNA")
	static void WriteDNAVertexDeltaInBox(
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
		FString& OutError);

	/**
	 * Build a groom binding for a character's face, the way the MetaHuman
	 * assemble does it.
	 *
	 * WHY THIS EXISTS. Two nights were spent on
	 * UGroomLibrary::CreateNewGroomBindingAssetWithPath, which is reflected,
	 * succeeds, saves, and produces a binding the renderer draws as a BALD
	 * CROWN with a clump of strands hanging at the jaw. It is not the call the
	 * pipeline uses. MetaHumanGroomEditorPipeline.cpp never creates a binding
	 * from scratch -- it DUPLICATES an already-built one and retargets it:
	 *
	 *     CharacterBinding = DuplicateObject(VendorBinding)
	 *     CharacterBinding->SetTargetSkeletalMesh(TargetMesh)
	 *     CharacterBinding->SetSourceSkeletalMesh(nullptr)
	 *     CharacterBinding->Build()
	 *
	 * That final Build() IS reflected -- and calling it through remote Python
	 * fatals the editor on `Assertion failed: IsUnlocked() [BulkData.cpp:596]`,
	 * the third MetaHuman/groom entry point to die that way after
	 * request_auto_rigging(blocking=True) and conform_to_target_meshes. The
	 * failure is a property of driving these subsystems synchronously through
	 * the transport, not of the API, which is exactly what a UFUNCTION in this
	 * module routes around: it runs on the game thread in the editor's own
	 * context.
	 *
	 * REFUSES rather than guessing when the source binding has no groom, when
	 * the target mesh is null, or when the destination package path is not a
	 * /Game path -- a binding written outside project content is the failure
	 * this whole investigation started from.
	 *
	 * THE RBF BAKE IS THE STEP THAT MATTERS, and it was measured to be so.
	 * A first version did duplicate + retarget + Build() and no bake: the
	 * editor survived and the render was still a bald crown at `crown 1%`. The
	 * deformation has to be baked INTO a duplicated groom, because the vendor
	 * groom is shaped for the archetype head and the binding alone does not
	 * move it. So this writes TWO assets -- a deformed groom and a binding
	 * that points at it -- and the caller must assign BOTH.
	 *
	 * @param SourceBinding      an ALREADY-BUILT binding, normally the vendor
	 *                           one shipped with the wardrobe item
	 * @param TargetMesh         the character's face mesh
	 * @param DestPackagePath    e.g. /Game/Characters/Foo/Grooms/BND_Bar
	 * @param DestGroomPath      where the RBF-deformed groom is written
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|Groom")
	// OverrideGroom: when null, the SourceBinding's own groom is duplicated
	// and deformed -- the stock-wardrobe case. When set, THAT groom is
	// deformed onto the target mesh instead, which is how a groom authored
	// in Blender gets bound: a custom .abc has no vendor binding of its own
	// to duplicate, and this recipe needs an already-built binding purely as
	// the source of the retarget. The binding is the vehicle, the groom is
	// the cargo, and before this parameter existed they could not be
	// separated.
	static void BuildGroomBindingForMesh(
		UGroomBindingAsset* SourceBinding,
		USkeletalMesh* TargetMesh,
		const FString& DestPackagePath,
		const FString& DestGroomPath,
		FString& OutBindingPath,
		FString& OutGroomPath,
		bool& bOutSuccess,
		FString& OutError,
		UGroomAsset* OverrideGroom = nullptr);

	/**
	 * Build a groom binding FROM SCRATCH for a groom that has none.
	 *
	 * WHY THIS EXISTS ALONGSIDE BuildGroomBindingForMesh. That one duplicates
	 * an already-built vendor binding, which is right for a stock wardrobe
	 * groom because the binding already matches it. It is structurally wrong
	 * for a groom authored in Blender: the duplicated binding carries
	 * per-strand root correspondence belonging to the DONOR's groom, and the
	 * measured symptom is that the DONOR alone decides where the strands land
	 * -- one donor put a clump over the character's eye, another rendered
	 * nothing at all, 10.3% of the frame apart on the same groom.
	 *
	 * Here the correspondence is COMPUTED for the groom's own roots instead of
	 * inherited. `FHairStrandsCore::CreateGroomBindingAsset` is the engine's
	 * own creator, and Build() then owns the deformation -- which is why this
	 * path deliberately does NOT run the RBF bake that R-GROOMBIND3 needs.
	 * Doing both would deform twice.
	 *
	 * SourceMesh may be null, in which case the target is used as the source
	 * and the binding is an identity -- the right choice when the groom was
	 * authored directly on the target's own topology.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab|Groom")
	static void BuildFreshGroomBinding(
		UGroomAsset* Groom,
		USkeletalMesh* SourceMesh,
		USkeletalMesh* TargetMesh,
		const FString& DestPackagePath,
		const FString& DestGroomPath,
		FString& OutBindingPath,
		FString& OutGroomPath,
		bool& bOutSuccess,
		FString& OutError,
		int32 NumInterpolationPoints = 100,
		int32 MatchingSection = 0);
};
