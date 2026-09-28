// Copyright Ryan B. LandscapeLab.
//
// The Game target exists so the project has a packaging path if one is ever
// wanted. Nothing in this project builds it today -- the deliverable is the
// Development Editor target. See LandscapeLabEditor.Target.cs for why
// ExtraModuleNames is empty.

using UnrealBuildTool;
using System.Collections.Generic;

public class LandscapeLabTarget : TargetRules
{
	public LandscapeLabTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
	}
}
