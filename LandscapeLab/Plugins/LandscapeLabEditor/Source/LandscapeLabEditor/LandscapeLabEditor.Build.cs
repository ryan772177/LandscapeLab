// Copyright Ryan B. LandscapeLab.

using UnrealBuildTool;

public class LandscapeLabEditor : ModuleRules
{
	public LandscapeLabEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// ALandscape, ALandscapeProxy::Import, ULandscapeSubsystem.
			"Landscape",
			// FLandscapeImportHelper, ELandscapeImportResult. Editor-only module,
			// which is why this plugin's module Type is "Editor".
			"LandscapeEditor",
			// GEditor, FActorLabelUtilities.
			"UnrealEd",
			"Slate",
			"SlateCore",

			// --- MetaHuman DNA joint editing (2026-08-17) ---
			// IDNAReader (GetJointCount / GetJointName /
			// GetNeutralJointTranslation), and LoadDNAFromFile /
			// SaveDNAToFile from DNAUtils.h. The DNA is the ONLY route to a
			// MetaHuman's neutral joints: the reflected Python surface
			// exposes a DNA READER (EvaluateRig -> vertices) and no joint
			// accessor at all, and the only reflected FACE write is
			// import_from_face_dna, which takes a whole file.
			"RigLogicModule",
			// FDNACalibDNAReader and
			// FDNACalibSetNeutralJointTranslationsCommand. This is the
			// engine's OWN DNACalib, which speaks the 2.5 format natively --
			// the public EpicGames/MetaHuman-DNA-Calibration bindings read
			// only 2.1 and hard-fail on this file.
			"DNACalibModule",

			// --- Groom binding (2026-08-20) ---
			// UGroomBindingAsset::Build(). The call IS reflected to Python and
			// FATALS the editor from remote exec on
			// `Assertion failed: IsUnlocked() [BulkData.cpp:596]` -- the third
			// MetaHuman/groom entry point to die that way. Running it here puts
			// it on the game thread in the editor own context instead.
			"HairStrandsCore",
		});
	}
}
