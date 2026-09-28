// Copyright Ryan B. LandscapeLab.

using UnrealBuildTool;

public class LandscapeLabGameplay : ModuleRules
{
	public LandscapeLabGameplay(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			// UEnhancedInputComponent, UInputAction, UInputMappingContext,
			// UEnhancedInputLocalPlayerSubsystem. Public because the character
			// header declares UInputAction* properties.
			"EnhancedInput",
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			// FInputActionValue and the EKeys used by the input bindings.
			"InputCore",
			// UNavigationSystemV1 and FNavLocation. The encounter director
			// REFUSES to spawn where a site will not project onto the navmesh,
			// so it needs the navigation system at runtime, not just at build
			// time -- an enemy on an unstreamed chunk stands still, which
			// reads as an AI bug and is a streaming bug.
			"NavigationSystem",
		});
	}
}
