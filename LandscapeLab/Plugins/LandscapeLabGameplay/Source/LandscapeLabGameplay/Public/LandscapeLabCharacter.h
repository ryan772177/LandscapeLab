// Copyright Ryan B. LandscapeLab.
//
// The player character. PHASE2_PLAN.md unit 5.
//
// WHY EVERY ASSET AND NUMBER IS A CONFIG PROPERTY AND NONE IS IN THE C++.
// Pipeline rule 2: every scene parameter comes from recipe JSON.
// recipes/character.json is the single declaration; scripts/apply_character_recipe.py
// projects it into DefaultGame.ini; this class reads that config at class
// load and applies it in PostInitializeComponents.
//
// The alternative -- ConstructorHelpers::FObjectFinder with literal /Game/
// paths -- would put a SECOND copy of every path in C++, where nothing would
// ever notice it drifting from the recipe. Config is what lets the recipe
// stay the source without needing a Blueprint asset in between.
//
// The walkable ANGLE is deliberately absent from every list here. Ruling 19
// makes it derived from a named movement profile, and a property for it would
// be exactly the second copy that rule exists to prevent.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "UObject/SoftObjectPath.h"
#include "LandscapeLabCharacter.generated.h"

class UCameraComponent;
class USkeletalMeshComponent;
class USpringArmComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

UCLASS(config = Game)
class LANDSCAPELABGAMEPLAY_API ALandscapeLabCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ALandscapeLabCharacter();

	/**
	 * Push recipes/character.json's movement block onto this character.
	 *
	 * Returns void with an explicit bOutSuccess rather than bool, because a
	 * UFUNCTION returning bool alongside out-params LOSES the bool in the
	 * Python binding -- Python receives (...outs) or None, so the failure
	 * flag disappears exactly when it is needed. That trap cost this project
	 * a session on 2026-08-12 and the convention is recorded in CLAUDE.md.
	 */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	void ApplyMovementSpec(float MaxWalkSpeedCmS,
	                       float MaxStepHeightCm,
	                       float JumpZVelocityCmS,
	                       float MaxAccelerationCmS2,
	                       float GravityScale,
	                       float CapsuleRadiusCm,
	                       float CapsuleHalfHeightCm,
	                       bool& bOutSuccess,
	                       FString& OutError);

	/** What was actually resolved at spawn, for a read-back that is not the
	 *  setter's own field. Empty entries name what could NOT be resolved. */
	UFUNCTION(BlueprintCallable, Category = "LandscapeLab")
	void GetResolvedSpec(FString& OutMesh, FString& OutAnimClass,
	                     FString& OutMappingContext, int32& OutBoundActions,
	                     FString& OutUnresolved) const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "LandscapeLab")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "LandscapeLab")
	TObjectPtr<UCameraComponent> FollowCamera;

	/** Carries FaceMeshPath's mesh when one resolves; empty otherwise. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "LandscapeLab")
	TObjectPtr<USkeletalMeshComponent> FaceMesh;

	// ---- config, projected from recipes/character.json ------------------

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Assets")
	FSoftObjectPath MeshPath;

	/**
	 * Optional SECOND skeletal mesh, posed by the primary one.
	 *
	 * A MetaHuman is not one mesh. Measured 2026-08-16 on MHC_AlpineHero: the
	 * body is metahuman_base_skel (342 bones) and the face is
	 * Face_Archetype_Skeleton (875 bones) -- two meshes, two skeletons -- while
	 * ACharacter owns exactly one Mesh (Character.h:352). So the face rides as
	 * its own component with the body as its LEADER POSE component, which is
	 * how MetaHuman's own preview actor is built (it carries Body and Face
	 * SkeletalMeshComponents side by side).
	 *
	 * ABSENT config leaves it null and this character behaves exactly as it
	 * did before, which is what keeps the mannequin path working.
	 */
	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Assets")
	FSoftObjectPath FaceMeshPath;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Assets")
	FSoftClassPath AnimClassPath;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Input")
	FSoftObjectPath MappingContextPath;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Input")
	FSoftObjectPath MoveActionPath;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Input")
	FSoftObjectPath LookActionPath;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Input")
	FSoftObjectPath JumpActionPath;

	/**
	 * Third-person boom length, and the radius it probes with.
	 *
	 * MEASURED DEFECT, 2026-08-16: at the spawn point the boom is inside the
	 * forest almost always -- 219,659 tree instances stand in this world -- so
	 * a 400 cm arm collapses onto a trunk and the first frame of the game is a
	 * 1 m close-up of the player's back. Turning the probe OFF is not the fix
	 * either; it puts the camera inside the canopy. A SMALLER PROBE with the
	 * test still on is what threads between the two, so both numbers are
	 * config rather than constants somebody has to rebuild to try.
	 *
	 * Zero means "not configured" and leaves the constructor's value, matching
	 * every other Cfg field here.
	 */
	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Camera")
	float CfgCameraArmLengthCm = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Camera")
	float CfgCameraProbeSizeCm = 0.0f;

	/** Raises the boom's pivot so the camera clears the shoulders. */
	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Camera")
	float CfgCameraSocketOffsetZCm = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgMaxWalkSpeedCmS = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgMaxStepHeightCm = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgJumpZVelocityCmS = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgMaxAccelerationCmS2 = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgGravityScale = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgCapsuleRadiusCm = 0.0f;

	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgCapsuleHalfHeightCm = 0.0f;

	/**
	 * Steepest ground this character treats as a floor.
	 *
	 * DERIVED, NEVER TYPED. apply_character_recipe resolves it from
	 * recipes/character.json's movement.profile against
	 * terrain_erosion.MOVEMENT_PROFILES and writes it here. Ruling 19 says
	 * the angle is declared once and derived; this ini value is a
	 * PROJECTION of that declaration, not a second copy of it, which is why
	 * the recipe still refuses to carry an angle of its own.
	 */
	UPROPERTY(config, EditDefaultsOnly, Category = "LandscapeLab|Movement")
	float CfgWalkableFloorAngleDeg = 0.0f;

	// Resolved at spawn. Not config -- these are the OUTCOME, and keeping
	// them separate is what lets GetResolvedSpec be a different instrument
	// from the config it read.
	UPROPERTY(Transient, BlueprintReadOnly, Category = "LandscapeLab|Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "LandscapeLab|Input")
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "LandscapeLab|Input")
	TObjectPtr<UInputAction> LookAction;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "LandscapeLab|Input")
	TObjectPtr<UInputAction> JumpAction;

protected:
	virtual void PostInitializeComponents() override;
	virtual void BeginPlay() override;
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

	void Move(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);

private:
	/** Names of config entries that were set but did not resolve. An asset
	 *  that failed to load must not read the same as one never configured. */
	UPROPERTY(Transient)
	TArray<FString> Unresolved;

	void ApplyConfiguredAssets();
	void ApplyConfiguredMovement();
};
