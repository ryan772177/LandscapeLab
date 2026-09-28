// Copyright Ryan B. LandscapeLab.
//
// LandscapeLab has NO primary game module, deliberately. All of this project's
// C++ lives in the LandscapeLabEditor plugin under Plugins/, which the engine
// discovers and enables on its own:
//
//   PluginManager.cpp:421-425 -- a plugin whose descriptor says
//   EnabledByDefault and whose GetLoadedFrom() is EPluginLoadedFrom::Project
//   returns true unconditionally, with no .uproject entry involved.
//
// That is what keeps this conversion off LandscapeLab.uproject entirely, and
// standing rule 4 ("never modify .uproject directly on disk") therefore still
// holds with no exception carved into it.
//
// ExtraModuleNames is empty for the same reason. UBT iterates it and does not
// require it to be non-empty (UEBuildTarget.cs:5025-5030); LaunchModuleName
// defaults to the engine's own "Launch" module for any non-Program target.

using UnrealBuildTool;
using System.Collections.Generic;

public class LandscapeLabEditorTarget : TargetRules
{
	public LandscapeLabEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
	}
}
